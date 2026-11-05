from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.models.hearing import Hearing, HearingReminder
from app.models.case import Case
from app.models.user import User
from app.schemas.hearing import ConflictOut, HearingCreate, HearingOut, HearingUpdate, Proceedings, ReminderIn, ReminderUpdate, Reschedule
from app.services.case_service import check_court, log, owned_case

ACTIVE = ('Scheduled', 'Awaiting Order')
DEFAULT_DURATION_MINUTES = 60

def owned_hearing(db: Session, user: User, hearing_id: UUID, lock=False):
    statement = select(Hearing).where(Hearing.id == hearing_id, Hearing.user_id == user.id)
    if lock: statement = statement.with_for_update()
    item = db.scalar(statement)
    if item is None or db.scalar(select(Case.id).where(Case.id == item.case_id, Case.user_id == user.id)) is None:
        raise HTTPException(404, 'Hearing not found')
    return item

def serialize(item):
    case = item.case; court = item.court
    return HearingOut.model_validate({**item.__dict__, 'case_title': case.case_title, 'case_number': case.case_number,
        'case_category': case.case_category, 'court_name': court.name if court else None,
        'court_district': court.district if court else None})

def list_hearings(db, user, limit=20, offset=0, from_date=None, to_date=None, court_id=None, status=None, category=None, case_id=None, sort='asc'):
    filters = [Hearing.user_id == user.id, Hearing.case.has(Case.user_id == user.id)]
    if from_date: filters.append(Hearing.hearing_date >= from_date)
    if to_date: filters.append(Hearing.hearing_date <= to_date)
    if court_id: filters.append(Hearing.court_id == court_id)
    if status: filters.append(Hearing.status == status)
    if category: filters.append(Hearing.case.has(Case.case_category == category))
    if case_id: filters.append(Hearing.case_id == case_id)
    total = db.scalar(select(func.count()).select_from(Hearing).where(*filters)) or 0
    order = (Hearing.hearing_date.desc(), Hearing.hearing_time.desc(), Hearing.id.desc()) if sort == 'desc' else (Hearing.hearing_date.asc(), Hearing.hearing_time.asc(), Hearing.id.asc())
    items = db.scalars(select(Hearing).options(selectinload(Hearing.case), selectinload(Hearing.court)).where(*filters).order_by(*order).offset(offset).limit(limit)).all()
    return total, [serialize(item) for item in items]

def create(db, user, data: HearingCreate):
    case = owned_case(db, user, data.case_id)
    court_id = data.court_id if data.court_id is not None else case.court_id
    check_court(db, user, court_id)
    values = data.model_dump(exclude={'court_id'})
    item = Hearing(user_id=user.id, court_id=court_id, status='Scheduled', **values)
    db.add(item); db.flush()
    log(db, user, case, 'hearing_scheduled', 'Hearing scheduled', details={'hearing_id': str(item.id), 'date': str(item.hearing_date)})
    db.commit()
    return serialize(owned_hearing(db, user, item.id))

def update(db, user, hearing_id, data: HearingUpdate):
    item = owned_hearing(db, user, hearing_id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, 'Provide at least one field')
    if item.status not in ACTIVE and any(k in changes for k in ('hearing_date', 'hearing_time', 'estimated_end_time')):
        raise HTTPException(409, 'Historical hearing date and time cannot be changed')
    if 'court_id' in changes: check_court(db, user, changes['court_id'])
    for required in ('hearing_date', 'hearing_type', 'purpose', 'reminder_enabled'):
        if required in changes and changes[required] is None: raise HTTPException(422, f'{required} cannot be null')
    start = changes.get('hearing_time', item.hearing_time); end = changes.get('estimated_end_time', item.estimated_end_time)
    if end and not start or end and start and end <= start: raise HTTPException(422, 'End time must follow start time')
    for key, value in changes.items(): setattr(item, key, value)
    if any(key in changes for key in ('hearing_date', 'hearing_time', 'reminder_enabled')): reschedule_reminders(db, item)
    log(db, user, item.case, 'hearing_updated', 'Hearing updated', details={'hearing_id': str(item.id), 'fields': list(changes)})
    db.commit()
    return serialize(owned_hearing(db, user, item.id))

def remove(db, user, hearing_id):
    item = owned_hearing(db, user, hearing_id)
    if item.status not in ACTIVE: raise HTTPException(409, 'Historical hearings cannot be deleted')
    log(db, user, item.case, 'hearing_cancelled', 'Hearing cancelled', details={'hearing_id': str(item.id)})
    item.status = 'Cancelled'
    reschedule_reminders(db, item)
    db.commit()

def proceedings(db, user, hearing_id, data: Proceedings, status):
    item = owned_hearing(db, user, hearing_id, lock=True)
    if item.status not in ACTIVE: raise HTTPException(409, 'Hearing already finalized')
    for key in ('proceedings_notes', 'judge_directions', 'adjournment_reason', 'outcome'):
        setattr(item, key, getattr(data, key))
    item.status = status
    item.next_hearing_date = data.next_hearing_date
    item.next_hearing_time = data.next_hearing_time
    if data.next_hearing_date:
        if data.next_hearing_date < item.hearing_date: raise HTTPException(422, 'Next hearing cannot precede the current hearing')
        if item.follow_up_hearing_id is None:
            next_item = Hearing(user_id=user.id, case_id=item.case_id, court_id=item.court_id, hearing_date=data.next_hearing_date,
                hearing_time=data.next_hearing_time, hearing_type=item.hearing_type, hearing_stage=item.hearing_stage,
                courtroom=item.courtroom, judge_name=item.judge_name, purpose=item.purpose,
                status='Scheduled', reminder_enabled=item.reminder_enabled)
            db.add(next_item); db.flush()
            item.follow_up_hearing_id = next_item.id
            log(db, user, item.case, 'hearing_scheduled', 'Follow-up hearing scheduled', details={'hearing_id': str(next_item.id), 'date': str(next_item.hearing_date)})
    reschedule_reminders(db, item)
    log(db, user, item.case, 'hearing_' + status.lower().replace(' ', '_'), 'Hearing ' + status.lower(), details={'hearing_id': str(item.id)})
    db.commit()
    return serialize(owned_hearing(db, user, item.id))

def reschedule(db, user, hearing_id, data: Reschedule):
    item = owned_hearing(db, user, hearing_id, lock=True)
    if item.status not in ACTIVE: raise HTTPException(409, 'Hearing already finalized')
    next_item = Hearing(user_id=user.id, case_id=item.case_id, court_id=item.court_id, hearing_date=data.hearing_date,
        hearing_time=data.hearing_time, estimated_end_time=data.estimated_end_time, hearing_type=item.hearing_type,
        hearing_stage=item.hearing_stage, courtroom=item.courtroom, judge_name=item.judge_name, purpose=item.purpose,
        status='Scheduled', reminder_enabled=item.reminder_enabled)
    item.status = 'Postponed'; item.adjournment_reason = data.reason; item.next_hearing_date = data.hearing_date; item.next_hearing_time = data.hearing_time
    db.add(next_item); db.flush(); item.follow_up_hearing_id = next_item.id
    reschedule_reminders(db, item)
    log(db, user, item.case, 'hearing_postponed', 'Hearing postponed', details={'hearing_id': str(item.id), 'next_hearing_id': str(next_item.id)})
    db.commit()
    return serialize(owned_hearing(db, user, item.id))

def conflicts(db, user, hearing_date, hearing_time=None, estimated_end_time=None, court_id=None, courtroom=None, exclude_id=None):
    filters = [Hearing.user_id == user.id, Hearing.hearing_date == hearing_date, Hearing.status.in_(ACTIVE)]
    if exclude_id: filters.append(Hearing.id != exclude_id)
    items = db.scalars(select(Hearing).options(selectinload(Hearing.case)).where(*filters)).all()
    results = []
    for item in items:
        if not hearing_time or not item.hearing_time:
            kind, reason = 'unknown_time', 'Hearing time is not specified'
        else:
            candidate_end = estimated_end_time or (datetime.combine(hearing_date, hearing_time) + timedelta(minutes=DEFAULT_DURATION_MINUTES)).time()
            other_end = item.estimated_end_time or (datetime.combine(hearing_date, item.hearing_time) + timedelta(minutes=DEFAULT_DURATION_MINUTES)).time()
            if hearing_time >= other_end or item.hearing_time >= candidate_end: continue
            same_room = bool(court_id and courtroom and court_id == item.court_id and courtroom.casefold() == (item.courtroom or '').casefold())
            kind = 'confirmed' if estimated_end_time and item.estimated_end_time else 'estimated'
            reason = 'Same courtroom overlap' if same_room else 'Advocate has overlapping hearings'
        results.append(ConflictOut(hearing_id=item.id, case_title=item.case.case_title, kind=kind, reason=reason))
    return results

def reminder_time(item, kind, custom=None, zone_name='Asia/Kolkata'):
    if kind == 'custom': return custom.astimezone(timezone.utc)
    zone = ZoneInfo(zone_name)
    local = datetime.combine(item.hearing_date, item.hearing_time or time(9, 0), zone)
    days = {'day_of': 0, 'one_day': 1, 'three_days': 3, 'one_week': 7}[kind]
    return (local - timedelta(days=days)).astimezone(timezone.utc)

def reschedule_reminders(db, item):
    for reminder in db.scalars(select(HearingReminder).where(HearingReminder.hearing_id == item.id, HearingReminder.status.in_(['pending', 'scheduled_local', 'retry']))).all():
        if not item.reminder_enabled or item.status not in ACTIVE: reminder.status = 'cancelled'
        elif reminder.reminder_type != 'custom':
            reminder.scheduled_at = reminder_time(item, reminder.reminder_type)
            reminder.status = 'pending'

def create_reminder(db, user, item, data: ReminderIn):
    if not item.reminder_enabled or item.status not in ACTIVE: raise HTTPException(409, 'Reminders are disabled for this hearing')
    if user.preferences and not user.preferences.hearing_reminders: raise HTTPException(409, 'Hearing reminders are disabled in notification settings')
    if data.delivery_channel == 'push': raise HTTPException(503, 'Push delivery is not configured')
    existing = db.scalar(select(HearingReminder).where(HearingReminder.hearing_id == item.id, HearingReminder.reminder_type == data.reminder_type, HearingReminder.delivery_channel == data.delivery_channel))
    scheduled = reminder_time(item, data.reminder_type, data.scheduled_at, user.preferences.timezone if user.preferences else 'Asia/Kolkata')
    if existing:
        existing.scheduled_at = scheduled; existing.status = 'pending'; reminder = existing
    else:
        reminder = HearingReminder(user_id=user.id, hearing_id=item.id, reminder_type=data.reminder_type,
            scheduled_at=scheduled, delivery_channel=data.delivery_channel, status='pending')
        db.add(reminder)
    db.commit(); db.refresh(reminder)
    return reminder

def update_reminder(db, user, item, reminder_id, data: ReminderUpdate):
    reminder = db.scalar(select(HearingReminder).where(HearingReminder.id == reminder_id, HearingReminder.hearing_id == item.id, HearingReminder.user_id == user.id))
    if not reminder: raise HTTPException(404, 'Reminder not found')
    changes = data.model_dump(exclude_unset=True)
    if 'scheduled_at' in changes:
        if not changes['scheduled_at'] or not changes['scheduled_at'].tzinfo: raise HTTPException(422, 'Timezone-aware scheduled_at required')
        reminder.scheduled_at = changes['scheduled_at'].astimezone(timezone.utc)
    if 'status' in changes: reminder.status = changes['status']
    db.commit(); db.refresh(reminder)
    return reminder

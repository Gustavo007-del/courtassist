import calendar
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from app.models.case import Case
from app.models.client import Client
from app.models.hearing import Hearing
from app.models.document import Document
from app.models.planning import Appointment, PlanningReminder, Task
from app.models.user import User


def zone(user: User):
    try: return ZoneInfo(user.preferences.timezone if user.preferences else 'Asia/Kolkata')
    except Exception: return ZoneInfo('Asia/Kolkata')


def today(user: User): return datetime.now(zone(user)).date()


def owned(db: Session, model, record_id, user: User):
    if record_id is None: return None
    record = db.get(model, record_id)
    if not record or record.user_id != user.id: raise HTTPException(404, 'Linked record not found')
    return record


def validate_links(db: Session, user: User, case_id=None, client_id=None, hearing_id=None, document_id=None):
    case = owned(db, Case, case_id, user)
    owned(db, Client, client_id, user)
    hearing = owned(db, Hearing, hearing_id, user)
    document = owned(db, Document, document_id, user)
    if hearing and case and hearing.case_id != case.id: raise HTTPException(422, 'Hearing is linked to another case')
    if document and case and document.case_id and document.case_id != case.id: raise HTTPException(422, 'Document is linked to another case')


def task_owned(db: Session, user: User, task_id):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id, Task.archived_at.is_(None)))
    if not task: raise HTTPException(404, 'Task not found')
    return task


def appointment_owned(db: Session, user: User, appointment_id):
    item = db.scalar(select(Appointment).where(Appointment.id == appointment_id, Appointment.user_id == user.id, Appointment.archived_at.is_(None)))
    if not item: raise HTTPException(404, 'Appointment not found')
    return item


def is_overdue(task: Task, user: User):
    if task.status in ('Completed', 'Cancelled') or task.archived_at or not task.due_date: return False
    deadline = datetime.combine(task.due_date, task.due_time or time(23, 59, 59), zone(user))
    return deadline < datetime.now(zone(user))


def overdue_at(instant: datetime):
    return or_(Task.due_date < instant.date(), and_(Task.due_date == instant.date(),
        func.coalesce(Task.due_time, time(23, 59, 59)) < instant.time()))


def task_data(task: Task, user: User):
    from app.schemas.planning import TaskOut
    return TaskOut.model_validate(task).model_copy(update={'is_overdue': is_overdue(task, user)})


def next_date(anchor: date, kind: str, interval: int):
    if kind == 'daily': return anchor + timedelta(days=interval)
    if kind == 'weekly': return anchor + timedelta(weeks=interval)
    if kind == 'custom': return anchor + timedelta(days=interval)
    if kind == 'monthly':
        month_index = anchor.year * 12 + anchor.month - 1 + interval
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))
    return anchor


def generate_recurrences(db: Session, user: User, root: Task, window_days: int = 60):
    if root.recurrence_kind == 'none' or not root.due_date or root.recurrence_root_id or root.archived_at: return 0
    end = today(user) + timedelta(days=window_days)
    existing = set(db.scalars(select(Task.occurrence_date).where(Task.recurrence_root_id == root.id)).all())
    candidate = root.due_date
    generated = 0
    for _ in range(1000):
        candidate = next_date(candidate, root.recurrence_kind, root.recurrence_interval)
        if candidate > end: break
        if candidate < today(user) or candidate in existing: continue
        item = Task(user_id=user.id, title=root.title, description=root.description, category=root.category,
                    priority=root.priority, status='Pending', due_date=candidate, due_time=root.due_time,
                    case_id=root.case_id, client_id=root.client_id, hearing_id=root.hearing_id,
                    document_id=root.document_id, reminder_minutes=root.reminder_minutes,
                    follow_up_notes=root.follow_up_notes, recurrence_kind='none', recurrence_root_id=root.id,
                    occurrence_date=candidate)
        db.add(item); db.flush(); sync_task_reminder(db, user, item)
        existing.add(candidate); generated += 1
        if generated >= 24: break
    return generated


def sync_task_reminder(db: Session, user: User, task: Task):
    reminder = db.scalar(select(PlanningReminder).where(PlanningReminder.task_id == task.id))
    enabled = user.preferences.task_reminders if user.preferences else True
    active = enabled and task.reminder_minutes is not None and task.due_date and task.status not in ('Completed', 'Cancelled') and not task.archived_at
    if not active:
        if reminder: reminder.status = 'cancelled'
        return
    due = datetime.combine(task.due_date, task.due_time or time(18, 0), zone(user))
    when = (due - timedelta(minutes=task.reminder_minutes)).astimezone(timezone.utc)
    if when <= datetime.now(timezone.utc):
        if reminder: reminder.status = 'cancelled'
        return
    if reminder: reminder.scheduled_at = when; reminder.status = 'pending'
    else: db.add(PlanningReminder(user_id=user.id, task_id=task.id, scheduled_at=when))


def sync_appointment_reminder(db: Session, user: User, item: Appointment):
    reminder = db.scalar(select(PlanningReminder).where(PlanningReminder.appointment_id == item.id))
    enabled = user.preferences.appointment_reminders if user.preferences else True
    active = enabled and item.reminder_minutes is not None and item.status == 'Scheduled' and not item.archived_at
    if not active:
        if reminder: reminder.status = 'cancelled'
        return
    start = datetime.combine(item.appointment_date, item.start_time, zone(user))
    when = (start - timedelta(minutes=item.reminder_minutes)).astimezone(timezone.utc)
    if when <= datetime.now(timezone.utc):
        if reminder: reminder.status = 'cancelled'
        return
    if reminder: reminder.scheduled_at = when; reminder.status = 'pending'
    else: db.add(PlanningReminder(user_id=user.id, appointment_id=item.id, scheduled_at=when))


def appointment_conflicts(db: Session, user: User, day: date, start: time, end: time, exclude_id=None):
    results = []
    others = db.scalars(select(Appointment).where(Appointment.user_id == user.id, Appointment.appointment_date == day,
                  Appointment.status == 'Scheduled', Appointment.archived_at.is_(None))).all()
    for other in others:
        if other.id != exclude_id and start < other.end_time and end > other.start_time:
            results.append({'kind': 'appointment', 'id': other.id, 'title': other.title, 'estimated': False})
    hearings = db.scalars(select(Hearing).where(Hearing.user_id == user.id, Hearing.hearing_date == day,
                  Hearing.status == 'Scheduled')).all()
    for hearing in hearings:
        if hearing.hearing_time is None:
            results.append({'kind': 'hearing', 'id': hearing.id, 'title': hearing.purpose, 'estimated': True})
            continue
        hearing_end = hearing.estimated_end_time or (datetime.combine(day, hearing.hearing_time) + timedelta(hours=1)).time()
        if start < hearing_end and end > hearing.hearing_time:
            results.append({'kind': 'hearing', 'id': hearing.id, 'title': hearing.purpose,
                            'estimated': hearing.estimated_end_time is None})
    return results

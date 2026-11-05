from datetime import date, timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.hearing import HearingReminder
from app.models.user import User
from app.schemas.hearing import ConflictOut, HearingCreate, HearingOut, HearingPage, HearingUpdate, Proceedings, ReminderIn, ReminderOut, ReminderUpdate, Reschedule
from app.services import hearing_service as service
from app.services.case_service import owned_case

router = APIRouter(tags=['hearings'])

def page(db, user, limit, offset, from_date=None, to_date=None, court_id=None, status=None, category=None, case_id=None, sort='asc'):
    total, items = service.list_hearings(db, user, limit, offset, from_date, to_date, court_id, status, category, case_id, sort)
    return HearingPage(items=items, total=total, limit=limit, offset=offset)

@router.get('/hearings', response_model=HearingPage)
def hearings(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), from_date: date | None = None, to_date: date | None = None, court_id: UUID | None = None, status: str | None = None, category: str | None = None, sort: Literal['asc', 'desc'] = 'asc'):
    return page(db, user, limit, offset, from_date, to_date, court_id, status, category, sort=sort)

@router.post('/hearings', response_model=HearingOut, status_code=201)
def create(data: HearingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.create(db, user, data)

@router.get('/hearings/conflicts', response_model=list[ConflictOut])
def conflicts(hearing_date: date, hearing_time: str | None = None, court_id: UUID | None = None, courtroom: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from datetime import time
    try: parsed_time = time.fromisoformat(hearing_time) if hearing_time else None
    except ValueError: raise HTTPException(422, 'Invalid hearing time')
    return service.conflicts(db, user, hearing_date, parsed_time, court_id=court_id, courtroom=courtroom)

@router.post('/hearings/check-conflicts', response_model=list[ConflictOut])
def check_conflicts(data: HearingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(db, user, data.case_id)
    return service.conflicts(db, user, data.hearing_date, data.hearing_time, data.estimated_end_time, data.court_id or case.court_id, data.courtroom)

@router.get('/hearings/{hearing_id}', response_model=HearingOut)
def detail(hearing_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.serialize(service.owned_hearing(db, user, hearing_id))

@router.patch('/hearings/{hearing_id}', response_model=HearingOut)
def update(hearing_id: UUID, data: HearingUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.update(db, user, hearing_id, data)

@router.delete('/hearings/{hearing_id}', status_code=204)
def cancel(hearing_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): service.remove(db, user, hearing_id)

@router.post('/hearings/{hearing_id}/complete', response_model=HearingOut)
def complete(hearing_id: UUID, data: Proceedings, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.proceedings(db, user, hearing_id, data, 'Completed')

@router.post('/hearings/{hearing_id}/adjourn', response_model=HearingOut)
def adjourn(hearing_id: UUID, data: Proceedings, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.proceedings(db, user, hearing_id, data, 'Adjourned')

@router.post('/hearings/{hearing_id}/reschedule', response_model=HearingOut)
def reschedule(hearing_id: UUID, data: Reschedule, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.reschedule(db, user, hearing_id, data)

@router.get('/cases/{case_id}/hearings', response_model=HearingPage)
def case_hearings(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    owned_case(db, user, case_id, include_archived=True)
    return page(db, user, limit, offset, case_id=case_id)

@router.get('/cases/{case_id}/hearings/history', response_model=HearingPage)
def case_history(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), status: str | None = None):
    owned_case(db, user, case_id, include_archived=True)
    return page(db, user, limit, offset, status=status, case_id=case_id, sort='desc')

@router.get('/calendar/hearings', response_model=HearingPage)
def calendar_hearings(from_date: date, to_date: date, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0), court_id: UUID | None = None, status: str | None = None, category: str | None = None):
    return page(db, user, limit, offset, from_date, to_date, court_id, status, category)

@router.get('/calendar/day', response_model=HearingPage)
def calendar_day(day: date, user: User = Depends(current_user), db: Session = Depends(get_db), court_id: UUID | None = None, status: str | None = None, category: str | None = None): return page(db, user, 100, 0, day, day, court_id, status, category)

@router.get('/calendar/day/conflicts', response_model=list[ConflictOut])
def calendar_day_conflicts(day: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(service.Hearing).where(service.Hearing.user_id == user.id, service.Hearing.hearing_date == day, service.Hearing.status == 'Scheduled')).all()
    warnings = {}
    for item in items:
        for warning in service.conflicts(db, user, item.hearing_date, item.hearing_time, item.estimated_end_time, item.court_id, item.courtroom, item.id):
            warnings[(str(warning.hearing_id), warning.kind)] = warning
    return list(warnings.values())

@router.get('/calendar/week', response_model=HearingPage)
def calendar_week(day: date, user: User = Depends(current_user), db: Session = Depends(get_db), court_id: UUID | None = None, status: str | None = None, category: str | None = None):
    start = day - timedelta(days=day.weekday())
    return page(db, user, 100, 0, start, start + timedelta(days=6), court_id, status, category)

@router.get('/calendar/month', response_model=HearingPage)
def calendar_month(year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12), user: User = Depends(current_user), db: Session = Depends(get_db), court_id: UUID | None = None, status: str | None = None, category: str | None = None):
    start = date(year, month, 1); end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return page(db, user, 100, 0, start, end, court_id, status, category)

@router.get('/hearings/{hearing_id}/reminders', response_model=list[ReminderOut])
def reminders(hearing_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.owned_hearing(db, user, hearing_id)
    return db.scalars(select(HearingReminder).where(HearingReminder.hearing_id == hearing_id, HearingReminder.user_id == user.id)).all()

@router.post('/hearings/{hearing_id}/reminders', response_model=ReminderOut, status_code=201)
def add_reminder(hearing_id: UUID, data: ReminderIn, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.create_reminder(db, user, service.owned_hearing(db, user, hearing_id), data)

@router.patch('/hearings/{hearing_id}/reminders/{reminder_id}', response_model=ReminderOut)
def update_reminder(hearing_id: UUID, reminder_id: UUID, data: ReminderUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.update_reminder(db, user, service.owned_hearing(db, user, hearing_id), reminder_id, data)

@router.delete('/hearings/{hearing_id}/reminders/{reminder_id}', status_code=204)
def delete_reminder(hearing_id: UUID, reminder_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = service.owned_hearing(db, user, hearing_id)
    reminder = db.scalar(select(HearingReminder).where(HearingReminder.id == reminder_id, HearingReminder.hearing_id == item.id, HearingReminder.user_id == user.id))
    if not reminder: raise HTTPException(404, 'Reminder not found')
    reminder.status = 'cancelled'; db.commit()

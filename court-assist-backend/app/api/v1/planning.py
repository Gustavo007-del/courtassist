from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.hearing import Hearing
from app.models.planning import Appointment, PlanningReminder, Task
from app.models.user import User
from app.schemas.planning import AppointmentInput, AppointmentOut, AppointmentPatch, ReminderOut, TaskInput, TaskOut, TaskPatch
from app.services import planning_service as service

router = APIRouter(tags=['planning'])


@router.get('/planning/reminders/upcoming', response_model=list[ReminderOut])
def upcoming_reminders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    enabled = []
    if not user.preferences or user.preferences.task_reminders: enabled.append(PlanningReminder.task_id.is_not(None))
    if not user.preferences or user.preferences.appointment_reminders: enabled.append(PlanningReminder.appointment_id.is_not(None))
    if not enabled: return []
    return db.scalars(select(PlanningReminder).where(PlanningReminder.user_id == user.id,
                      or_(*enabled),
                      PlanningReminder.status == 'pending', PlanningReminder.scheduled_at >= now,
                      PlanningReminder.scheduled_at <= now + timedelta(days=30)).order_by(PlanningReminder.scheduled_at).limit(100)).all()


def task_query(user, q=None, status=None, priority=None, category=None, case_id=None, from_date=None, to_date=None, archived=False):
    query = select(Task).where(Task.user_id == user.id, Task.archived_at.is_not(None) if archived else Task.archived_at.is_(None))
    if q: query = query.where(or_(Task.title.ilike(f'%{q}%'), Task.description.ilike(f'%{q}%')))
    if status: query = query.where(Task.status == status)
    if priority: query = query.where(Task.priority == priority)
    if category: query = query.where(Task.category == category)
    if case_id: query = query.where(Task.case_id == case_id)
    if from_date: query = query.where(Task.due_date >= from_date)
    if to_date: query = query.where(Task.due_date <= to_date)
    return query


@router.get('/tasks/overdue')
def overdue_tasks(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Task).where(Task.user_id == user.id, Task.archived_at.is_(None),
        Task.status.in_(['Pending', 'In Progress']), service.overdue_at(datetime.now(service.zone(user))))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Task.due_date, Task.due_time, Task.id).offset(offset).limit(limit)).all()
    return {'items': [service.task_data(task, user) for task in items], 'total': total, 'limit': limit, 'offset': offset}


@router.get('/tasks/upcoming')
def upcoming_tasks(days: int = Query(14, ge=1, le=90), user: User = Depends(current_user), db: Session = Depends(get_db)):
    start = service.today(user)
    items = db.scalars(select(Task).where(Task.user_id == user.id, Task.archived_at.is_(None), Task.status.in_(['Pending', 'In Progress']), Task.due_date >= start, Task.due_date <= start + timedelta(days=days)).order_by(Task.due_date, Task.due_time).limit(100)).all()
    return [service.task_data(task, user) for task in items]


@router.get('/tasks')
def list_tasks(q: str | None = Query(default=None, max_length=200), status: str | None = None, priority: str | None = None,
               category: str | None = None, case_id: UUID | None = None, from_date: date | None = None, to_date: date | None = None,
               archived: bool = False, sort: Literal['due', 'priority', 'created', 'status'] = 'due',
               limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    roots = db.scalars(select(Task).where(Task.user_id == user.id, Task.recurrence_kind != 'none', Task.recurrence_root_id.is_(None), Task.archived_at.is_(None)).with_for_update()).all()
    for root in roots: service.generate_recurrences(db, user, root)
    db.commit()
    query = task_query(user, q, status, priority, category, case_id, from_date, to_date, archived)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    priority_order = case((Task.priority == 'Urgent', 4), (Task.priority == 'High', 3), (Task.priority == 'Medium', 2), else_=1)
    ordering = {'due': (Task.due_date.asc().nulls_last(), Task.due_time.asc()), 'priority': (priority_order.desc(), Task.due_date.asc()), 'created': (Task.created_at.desc(),), 'status': (Task.status.asc(), Task.due_date.asc())}[sort]
    items = db.scalars(query.order_by(*ordering).offset(offset).limit(limit)).all()
    return {'items': [service.task_data(item, user) for item in items], 'total': total, 'limit': limit, 'offset': offset}


@router.post('/tasks', response_model=TaskOut, status_code=201)
def create_task(data: TaskInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.validate_links(db, user, data.case_id, data.client_id, data.hearing_id, data.document_id)
    task = Task(id=db.info.get("sync_record_id"), user_id=user.id, **data.model_dump())
    if task.status == 'Completed': task.completed_at = datetime.now(timezone.utc)
    db.add(task); db.flush(); service.sync_task_reminder(db, user, task); service.generate_recurrences(db, user, task); db.commit(); db.refresh(task)
    return service.task_data(task, user)


@router.get('/tasks/{task_id}', response_model=TaskOut)
def get_task(task_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.task_data(service.task_owned(db, user, task_id), user)


@router.patch('/tasks/{task_id}', response_model=TaskOut)
def patch_task(task_id: UUID, data: TaskPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = service.task_owned(db, user, task_id)
    current = {name: getattr(task, name) for name in TaskInput.model_fields}
    changes = data.model_dump(exclude_unset=True)
    merged = TaskInput.model_validate({**current, **changes})
    service.validate_links(db, user, merged.case_id, merged.client_id, merged.hearing_id, merged.document_id)
    for key, value in changes.items(): setattr(task, key, value)
    if task.status == 'Completed' and not task.completed_at: task.completed_at = datetime.now(timezone.utc)
    if task.status != 'Completed': task.completed_at = None
    service.sync_task_reminder(db, user, task)
    if task.recurrence_root_id is None: service.generate_recurrences(db, user, task)
    db.commit(); db.refresh(task)
    return service.task_data(task, user)


@router.delete('/tasks/{task_id}', status_code=204)
def archive_task(task_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = service.task_owned(db, user, task_id); task.archived_at = datetime.now(timezone.utc)
    service.sync_task_reminder(db, user, task); db.commit()


@router.post('/tasks/{task_id}/complete', response_model=TaskOut)
def complete_task(task_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = service.task_owned(db, user, task_id); task.status = 'Completed'; task.completed_at = datetime.now(timezone.utc)
    service.sync_task_reminder(db, user, task); db.commit(); db.refresh(task); return service.task_data(task, user)


@router.post('/tasks/{task_id}/reopen', response_model=TaskOut)
def reopen_task(task_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = service.task_owned(db, user, task_id)
    if task.status != 'Completed': raise HTTPException(409, 'Only completed tasks can be reopened')
    task.status = 'Pending'; task.completed_at = None
    service.sync_task_reminder(db, user, task); db.commit(); db.refresh(task); return service.task_data(task, user)


@router.get('/tasks/{task_id}/reminders', response_model=list[ReminderOut])
def task_reminders(task_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.task_owned(db, user, task_id)
    return db.scalars(select(PlanningReminder).where(PlanningReminder.task_id == task_id, PlanningReminder.user_id == user.id)).all()


def appointment_query(user, q=None, status=None, appointment_type=None, from_date=None, to_date=None, case_id=None, client_id=None):
    query = select(Appointment).where(Appointment.user_id == user.id, Appointment.archived_at.is_(None))
    if q: query = query.where(or_(Appointment.title.ilike(f'%{q}%'), Appointment.description.ilike(f'%{q}%')))
    for field, value in ((Appointment.status, status), (Appointment.appointment_type, appointment_type), (Appointment.case_id, case_id), (Appointment.client_id, client_id)):
        if value is not None: query = query.where(field == value)
    if from_date: query = query.where(Appointment.appointment_date >= from_date)
    if to_date: query = query.where(Appointment.appointment_date <= to_date)
    return query


@router.get('/appointments/upcoming', response_model=list[AppointmentOut])
def upcoming_appointments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(appointment_query(user, status='Scheduled', from_date=service.today(user)).order_by(Appointment.appointment_date, Appointment.start_time).limit(100)).all()


@router.get('/appointments/calendar', response_model=list[AppointmentOut])
def appointment_calendar(from_date: date, to_date: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(appointment_query(user, from_date=from_date, to_date=to_date).order_by(Appointment.appointment_date, Appointment.start_time).limit(300)).all()


@router.post('/appointments/check-conflicts')
def check_conflicts(data: AppointmentInput, appointment_id: UUID | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if appointment_id: service.appointment_owned(db, user, appointment_id)
    return service.appointment_conflicts(db, user, data.appointment_date, data.start_time, data.end_time, appointment_id)


@router.get('/appointments')
def list_appointments(q: str | None = Query(default=None, max_length=200), status: str | None = None,
                      appointment_type: str | None = None, from_date: date | None = None, to_date: date | None = None,
                      case_id: UUID | None = None, client_id: UUID | None = None,
                      limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = appointment_query(user, q, status, appointment_type, from_date, to_date, case_id, client_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Appointment.appointment_date.desc(), Appointment.start_time).offset(offset).limit(limit)).all()
    return {'items': [AppointmentOut.model_validate(item) for item in items], 'total': total, 'limit': limit, 'offset': offset}


@router.post('/appointments', response_model=AppointmentOut, status_code=201)
def create_appointment(data: AppointmentInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.services.sync_feed import advisory_lock
    advisory_lock(db, f"courtassist-appointments:{user.id}")
    service.validate_links(db, user, data.case_id, data.client_id)
    item = Appointment(id=db.info.get("sync_record_id"), user_id=user.id, **data.model_dump())
    db.add(item); db.flush(); service.sync_appointment_reminder(db, user, item); db.commit(); db.refresh(item)
    return item


@router.get('/appointments/{appointment_id}', response_model=AppointmentOut)
def get_appointment(appointment_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.appointment_owned(db, user, appointment_id)


@router.patch('/appointments/{appointment_id}', response_model=AppointmentOut)
def patch_appointment(appointment_id: UUID, data: AppointmentPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.services.sync_feed import advisory_lock
    advisory_lock(db, f"courtassist-appointments:{user.id}")
    item = service.appointment_owned(db, user, appointment_id)
    current = {name: getattr(item, name) for name in AppointmentInput.model_fields}
    changes = data.model_dump(exclude_unset=True)
    merged = AppointmentInput.model_validate({**current, **changes})
    service.validate_links(db, user, merged.case_id, merged.client_id)
    for key, value in changes.items(): setattr(item, key, value)
    service.sync_appointment_reminder(db, user, item); db.commit(); db.refresh(item)
    return item


@router.delete('/appointments/{appointment_id}', status_code=204)
def archive_appointment(appointment_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = service.appointment_owned(db, user, appointment_id); item.archived_at = datetime.now(timezone.utc)
    service.sync_appointment_reminder(db, user, item); db.commit()


@router.post('/appointments/{appointment_id}/cancel', response_model=AppointmentOut)
def cancel_appointment(appointment_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = service.appointment_owned(db, user, appointment_id); item.status = 'Cancelled'
    service.sync_appointment_reminder(db, user, item); db.commit(); db.refresh(item); return item


@router.get('/appointments/{appointment_id}/reminders', response_model=list[ReminderOut])
def appointment_reminders(appointment_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.appointment_owned(db, user, appointment_id)
    return db.scalars(select(PlanningReminder).where(PlanningReminder.appointment_id == appointment_id, PlanningReminder.user_id == user.id)).all()


@router.get('/calendar/agenda')
def agenda(from_date: date, to_date: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if to_date < from_date or (to_date - from_date).days > 62: raise HTTPException(422, 'Calendar range must be within 62 days')
    hearings = db.scalars(select(Hearing).where(Hearing.user_id == user.id, Hearing.hearing_date >= from_date, Hearing.hearing_date <= to_date, Hearing.status == 'Scheduled')).all()
    tasks = db.scalars(select(Task).where(Task.user_id == user.id, Task.archived_at.is_(None), Task.due_date >= from_date, Task.due_date <= to_date)).all()
    appointments = db.scalars(appointment_query(user, from_date=from_date, to_date=to_date)).all()
    rows = ([{'kind': 'hearing', 'id': item.id, 'date': item.hearing_date, 'time': item.hearing_time, 'title': item.purpose} for item in hearings] +
            [{'kind': 'task', 'id': item.id, 'date': item.due_date, 'time': item.due_time, 'title': item.title, 'status': item.status} for item in tasks] +
            [{'kind': 'appointment', 'id': item.id, 'date': item.appointment_date, 'time': item.start_time, 'title': item.title, 'status': item.status} for item in appointments])
    return sorted(rows, key=lambda row: (row['date'], row['time'] or time(23, 59)))

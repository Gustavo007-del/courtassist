from datetime import datetime, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.case import Case
from app.models.hearing import Hearing
from app.models.court import Court
from app.models.user import User
from app.models.planning import Task, Appointment
from app.services.planning_service import overdue_at
from app.schemas.dashboard import DashboardOut, DashboardProfile, DashboardSummary, ModuleAvailability
from app.services.activity_service import list_activities


def overview(db: Session, user: User) -> DashboardOut:
    timezone_name = user.preferences.timezone if user.preferences else 'Asia/Kolkata'
    now = datetime.now(ZoneInfo(timezone_name))
    today = now.date()
    _, recent = list_activities(db, user, limit=8, offset=0)
    _, today_entries = list_activities(db, user, limit=8, offset=0, from_date=today, to_date=today)
    active_cases = db.scalar(select(func.count()).select_from(Case).where(Case.user_id == user.id, Case.is_archived.is_(False), Case.current_status.not_in(['Disposed', 'Dismissed', 'Withdrawn', 'Settled', 'Transferred']))) or 0
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=6 - today.weekday())
    today_hearings = db.scalar(select(func.count()).select_from(Hearing).where(Hearing.user_id == user.id, Hearing.hearing_date == today, Hearing.status == 'Scheduled')) or 0
    tomorrow_hearings = db.scalar(select(func.count()).select_from(Hearing).where(Hearing.user_id == user.id, Hearing.hearing_date == tomorrow, Hearing.status == 'Scheduled')) or 0
    week_hearings = db.scalar(select(func.count()).select_from(Hearing).where(Hearing.user_id == user.id, Hearing.hearing_date >= today, Hearing.hearing_date <= week_end, Hearing.status == 'Scheduled')) or 0
    scheduled = db.execute(select(Hearing, Case.case_title, Case.case_number, Court.name).join(Case, Hearing.case_id == Case.id).outerjoin(Court, Hearing.court_id == Court.id).where(Hearing.user_id == user.id, Hearing.hearing_date == today, Hearing.status == 'Scheduled').order_by(Hearing.hearing_time)).all()
    schedule = [dict(id=hearing.id, hearing_time=datetime.combine(today, hearing.hearing_time, ZoneInfo(timezone_name)) if hearing.hearing_time else None, case_title=title, case_number=number, court_name=court_name or '', hearing_purpose=hearing.purpose) for hearing, title, number, court_name in scheduled]
    upcoming = db.execute(select(Hearing, Case.case_title).join(Case, Hearing.case_id == Case.id).where(Hearing.user_id == user.id, Hearing.hearing_date >= today, Hearing.status == 'Scheduled').order_by(Hearing.hearing_date, Hearing.hearing_time).limit(8)).all()
    recent_completed = db.scalar(select(func.count()).select_from(Hearing).where(Hearing.user_id == user.id, Hearing.status == 'Completed', Hearing.hearing_date >= today - timedelta(days=7), Hearing.hearing_date <= today)) or 0
    from app.services.hearing_service import ACTIVE, times_overlap
    active_hearings = db.scalars(select(Hearing).where(Hearing.user_id == user.id, Hearing.hearing_date == today,
        Hearing.status.in_(ACTIVE))).all()
    conflict_count = sum(int(a.status == 'Scheduled') + int(b.status == 'Scheduled')
        for a, b in combinations(active_hearings, 2)
        if times_overlap(today, a.hearing_time, a.estimated_end_time, b.hearing_time, b.estimated_end_time))
    pending, tasks_due_today, overdue_tasks, upcoming_deadlines, high_priority = db.execute(select(
        func.count(), func.count().filter(Task.due_date == today), func.count().filter(overdue_at(now)),
        func.count().filter(Task.due_date.between(today, today + timedelta(days=7))),
        func.count().filter(Task.priority.in_(('High', 'Urgent'))),
    ).where(Task.user_id == user.id, Task.archived_at.is_(None), Task.status.in_(['Pending', 'In Progress']))).one()
    upcoming_appointments = db.scalar(select(func.count()).select_from(Appointment).where(Appointment.user_id == user.id, Appointment.archived_at.is_(None), Appointment.status == 'Scheduled', Appointment.appointment_date >= today, Appointment.appointment_date <= today + timedelta(days=7))) or 0
    recent_completed_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.user_id == user.id, Task.status == 'Completed', Task.completed_at >= datetime.now(ZoneInfo(timezone_name)) - timedelta(days=7))) or 0
    return DashboardOut(
        profile=DashboardProfile(id=user.id, full_name=user.full_name,
                                 profile_image=user.profile_image,
                                 professional_designation=user.professional_designation),
        today_date=today, timezone=timezone_name,
        summary=DashboardSummary(today_hearings=today_hearings, tomorrow_hearings=tomorrow_hearings,
                                 active_cases=active_cases, pending_tasks=pending,
                                 overdue_tasks=overdue_tasks, upcoming_deadlines=upcoming_deadlines,
                                 tasks_due_today=tasks_due_today, high_priority_tasks=high_priority,
                                 upcoming_appointments=upcoming_appointments, recently_completed_tasks=recent_completed_tasks),
        module_availability=ModuleAvailability(cases=True, hearings=True, tasks=True, appointments=True, deadlines=True),
        today_schedule=schedule, today_activities=today_entries,
        upcoming_activities=[dict(id=hearing.id, activity_type='hearing_scheduled', title=title, hearing_date=hearing.hearing_date, scheduled_at=datetime.combine(hearing.hearing_date, hearing.hearing_time, ZoneInfo(timezone_name)) if hearing.hearing_time else None, entity_type='hearing', entity_id=hearing.id) for hearing, title in upcoming], recent_activities=recent,
        hearing_summary={'this_week': week_hearings, 'recently_completed': recent_completed, 'potential_conflicts_today': conflict_count},
    )

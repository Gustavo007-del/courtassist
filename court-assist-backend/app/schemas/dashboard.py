from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from app.schemas.activity import ActivityOut


class DashboardProfile(BaseModel):
    id: UUID
    full_name: str
    profile_image: str | None
    professional_designation: str | None


class DashboardSummary(BaseModel):
    today_hearings: int | None
    tomorrow_hearings: int | None
    active_cases: int | None
    pending_tasks: int | None
    overdue_tasks: int | None
    upcoming_deadlines: int | None


class ModuleAvailability(BaseModel):
    cases: bool = False
    hearings: bool = False
    tasks: bool = False
    appointments: bool = False
    deadlines: bool = False
    payments: bool = False


class ScheduleEntry(BaseModel):
    id: UUID
    hearing_time: datetime | None
    case_title: str
    case_number: str
    court_name: str
    hearing_purpose: str | None


class UpcomingEntry(BaseModel):
    id: UUID
    activity_type: str
    title: str
    scheduled_at: datetime | None
    hearing_date: date | None = None
    entity_type: str | None
    entity_id: UUID | None


class DashboardOut(BaseModel):
    profile: DashboardProfile
    today_date: date
    timezone: str
    summary: DashboardSummary
    module_availability: ModuleAvailability
    today_schedule: list[ScheduleEntry]
    today_activities: list[ActivityOut]
    upcoming_activities: list[UpcomingEntry]
    recent_activities: list[ActivityOut]
    hearing_summary: dict = {}

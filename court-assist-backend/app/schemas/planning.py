from datetime import date, datetime, time
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskPriority = Literal['Low', 'Medium', 'High', 'Urgent']
TaskStatus = Literal['Pending', 'In Progress', 'Completed', 'Cancelled']
TaskCategory = Literal['Filing', 'Prepare counter affidavit', 'Collect documents', 'Client contact', 'Arguments preparation', 'Certified copy', 'Application filing', 'Court fee payment', 'Follow-up', 'Legal research', 'General']
Recurrence = Literal['none', 'daily', 'weekly', 'monthly', 'custom']
AppointmentType = Literal['Client consultation', 'Client meeting', 'Office appointment', 'Phone call', 'Video consultation', 'Document discussion', 'General appointment']
AppointmentStatus = Literal['Scheduled', 'Completed', 'Cancelled', 'No-show']


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=10000)
    category: TaskCategory = 'General'
    priority: TaskPriority = 'Medium'
    status: TaskStatus = 'Pending'
    start_date: date | None = None
    due_date: date | None = None
    due_time: time | None = None
    case_id: UUID | None = None
    client_id: UUID | None = None
    hearing_id: UUID | None = None
    document_id: UUID | None = None
    recurrence_kind: Recurrence = 'none'
    recurrence_interval: int = Field(default=1, ge=1, le=365)
    reminder_minutes: int | None = Field(default=None, ge=0, le=43200)
    follow_up_notes: str = Field(default='', max_length=10000)

    @model_validator(mode='after')
    def dates_valid(self):
        if self.due_time and not self.due_date: raise ValueError('Due time requires a due date')
        if self.start_date and self.due_date and self.start_date > self.due_date: raise ValueError('Start date must not follow due date')
        if self.recurrence_kind != 'none' and not self.due_date: raise ValueError('Recurring tasks require a due date')
        return self


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    category: TaskCategory | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    start_date: date | None = None
    due_date: date | None = None
    due_time: time | None = None
    case_id: UUID | None = None
    client_id: UUID | None = None
    hearing_id: UUID | None = None
    document_id: UUID | None = None
    recurrence_kind: Recurrence | None = None
    recurrence_interval: int | None = Field(default=None, ge=1, le=365)
    reminder_minutes: int | None = Field(default=None, ge=0, le=43200)
    follow_up_notes: str | None = Field(default=None, max_length=10000)


class TaskOut(TaskInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    completed_at: datetime | None
    recurrence_root_id: UUID | None
    occurrence_date: date | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False


class AppointmentInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=10000)
    appointment_type: AppointmentType = 'General appointment'
    appointment_date: date
    start_time: time
    end_time: time
    location: str = Field(default='', max_length=500)
    meeting_mode: Literal['In person', 'Phone', 'Video'] = 'In person'
    client_id: UUID | None = None
    case_id: UUID | None = None
    attendee_details: str = Field(default='', max_length=500)
    reminder_minutes: int | None = Field(default=None, ge=0, le=43200)
    status: AppointmentStatus = 'Scheduled'
    private_notes: str = Field(default='', max_length=10000)

    @model_validator(mode='after')
    def time_valid(self):
        if self.end_time <= self.start_time: raise ValueError('End time must follow start time')
        return self


class AppointmentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    appointment_type: AppointmentType | None = None
    appointment_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=500)
    meeting_mode: Literal['In person', 'Phone', 'Video'] | None = None
    client_id: UUID | None = None
    case_id: UUID | None = None
    attendee_details: str | None = Field(default=None, max_length=500)
    reminder_minutes: int | None = Field(default=None, ge=0, le=43200)
    status: AppointmentStatus | None = None
    private_notes: str | None = Field(default=None, max_length=10000)


class AppointmentOut(AppointmentInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID | None
    appointment_id: UUID | None
    scheduled_at: datetime
    status: str

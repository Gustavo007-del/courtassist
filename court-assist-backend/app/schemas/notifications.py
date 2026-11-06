from datetime import datetime,date,time
from typing import Annotated,Literal
from uuid import UUID
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from pydantic import Field,field_validator,model_validator
from app.schemas.practice import Input,patch_schema

class NotificationPreferences(Input):
    push_notifications: bool=False
    local_notifications: bool=True
    email_notifications: bool=False
    hearing_reminders: bool=True
    task_reminders: bool=True
    appointment_reminders: bool=True
    payment_reminders: bool=True
    document_reminders: bool=False
    draft_reminders: bool=False
    daily_summary: bool=False
    hearing_auto_reminders: bool=False
    hearing_reminder_days: list[Annotated[int,Field(ge=0,le=30)]]=Field(default_factory=lambda:[1],max_length=10)
    reminder_time: time=time(9)
    daily_summary_time: time=time(8)
    quiet_start: time|None=None
    quiet_end: time|None=None
    urgent_quiet_override: bool=False
    task_due_today: bool=False
    task_overdue_alerts: bool=False
    task_high_priority: bool=False
    overdue_repeat_days: Annotated[int,Field(ge=1,le=30)]|None=None
    payment_due_days: Annotated[int,Field(ge=0,le=30)]=1
    finance_auto_reminders: bool=False
    timezone: Annotated[str,Field(max_length=64)]='Asia/Kolkata'

    @field_validator('timezone')
    @classmethod
    def zone(cls,value):
        try:ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):raise ValueError('Invalid timezone')
        return value
    @field_validator('hearing_reminder_days')
    @classmethod
    def intervals(cls,value):return sorted(set(value))
    @field_validator('reminder_time','daily_summary_time','quiet_start','quiet_end')
    @classmethod
    def wall_clock(cls,value):
        if value and (value.tzinfo or value.second or value.microsecond):raise ValueError('Use local HH:MM without an offset or seconds')
        return value
    @model_validator(mode='after')
    def quiet(self):
        if (self.quiet_start is None)!=(self.quiet_end is None):raise ValueError('Set both quiet-hour times, or neither')
        if self.quiet_start and self.quiet_start==self.quiet_end:raise ValueError('Quiet hours must have different start and end times')
        return self

PreferencesPatch=patch_schema('NotificationPreferencesPatch',NotificationPreferences)

class RegisterDevice(Input):
    reactivate: bool=False
    installation_id: UUID
    platform: Literal['android','ios']
    label: Annotated[str,Field(max_length=80)]=''
    token: Annotated[str,Field(min_length=20,max_length=4096)]|None=None

class LocalAcknowledgement(Input):
    device_id: UUID
    notification_id: UUID
    scheduled_at: datetime
    @field_validator('scheduled_at')
    @classmethod
    def aware(cls,value):
        if not value.tzinfo:raise ValueError('Timezone-aware scheduled_at is required')
        return value

class ManualReminder(Input):
    replaces: UUID|None=None
    entity_type: Literal['document','draft','agreement','invoice']
    entity_id: UUID
    scheduled_at: datetime|None=None
    local_date: date|None=None
    local_time: time|None=None
    priority: Literal['normal','high','urgent']='normal'
    purpose: Literal['review','filing','collection','general','payment']='general'
    @model_validator(mode='after')
    def instant(self):
        if self.scheduled_at:
            if not self.scheduled_at.tzinfo:raise ValueError('Timezone-aware scheduled_at required')
            if self.local_date or self.local_time:raise ValueError('Use an instant or a local date and time, not both')
        elif not self.local_date or not self.local_time:raise ValueError('Provide a reminder date and time')
        if self.local_time and self.local_time.tzinfo:raise ValueError('Local time must not include an offset')
        return self

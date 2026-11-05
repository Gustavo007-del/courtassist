from datetime import date, datetime, time
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

HearingStatus = Literal['Scheduled', 'Completed', 'Adjourned', 'Cancelled', 'Postponed', 'Awaiting Order']
ReminderType = Literal['day_of', 'one_day', 'three_days', 'one_week', 'custom']

class HearingFields(BaseModel):
    case_id: UUID
    court_id: UUID | None = None
    hearing_date: date
    hearing_time: time | None = None
    estimated_end_time: time | None = None
    hearing_type: str = Field(min_length=2, max_length=80)
    hearing_stage: str | None = Field(default=None, max_length=160)
    courtroom: str | None = Field(default=None, max_length=120)
    judge_name: str | None = Field(default=None, max_length=160)
    purpose: str = Field(min_length=2, max_length=1000)
    reminder_enabled: bool = True

    @model_validator(mode='after')
    def valid_time(self):
        if self.estimated_end_time and not self.hearing_time: raise ValueError('Start time required when end time is set')
        if self.estimated_end_time and self.hearing_time and self.estimated_end_time <= self.hearing_time: raise ValueError('End time must follow start time')
        return self

class HearingCreate(HearingFields): pass

class HearingUpdate(BaseModel):
    court_id: UUID | None = None
    hearing_date: date | None = None
    hearing_time: time | None = None
    estimated_end_time: time | None = None
    hearing_type: str | None = Field(default=None, min_length=2, max_length=80)
    hearing_stage: str | None = Field(default=None, max_length=160)
    courtroom: str | None = Field(default=None, max_length=120)
    judge_name: str | None = Field(default=None, max_length=160)
    purpose: str | None = Field(default=None, min_length=2, max_length=1000)
    proceedings_notes: str | None = Field(default=None, max_length=10000)
    judge_directions: str | None = Field(default=None, max_length=10000)
    adjournment_reason: str | None = Field(default=None, max_length=1000)
    outcome: str | None = Field(default=None, max_length=10000)
    reminder_enabled: bool | None = None

class Proceedings(BaseModel):
    proceedings_notes: str | None = Field(default=None, max_length=10000)
    judge_directions: str | None = Field(default=None, max_length=10000)
    adjournment_reason: str | None = Field(default=None, max_length=1000)
    outcome: str | None = Field(default=None, max_length=10000)
    next_hearing_date: date | None = None
    next_hearing_time: time | None = None
    @model_validator(mode='after')
    def next_time_requires_date(self):
        if self.next_hearing_time and not self.next_hearing_date: raise ValueError('Next hearing date required')
        return self

class Reschedule(BaseModel):
    hearing_date: date
    hearing_time: time | None = None
    estimated_end_time: time | None = None
    reason: str | None = Field(default=None, max_length=1000)
    @model_validator(mode='after')
    def valid_time(self):
        if self.estimated_end_time and not self.hearing_time: raise ValueError('Start time required')
        if self.estimated_end_time and self.hearing_time and self.estimated_end_time <= self.hearing_time: raise ValueError('End time must follow start time')
        return self

class HearingOut(HearingFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; status: HearingStatus; proceedings_notes: str | None; judge_directions: str | None
    adjournment_reason: str | None; outcome: str | None; next_hearing_date: date | None; next_hearing_time: time | None
    follow_up_hearing_id: UUID | None; created_at: datetime; updated_at: datetime
    case_title: str; case_number: str; case_category: str; court_name: str | None; court_district: str | None

class HearingPage(BaseModel):
    items: list[HearingOut]; total: int; limit: int; offset: int

class ConflictOut(BaseModel):
    hearing_id: UUID
    case_title: str
    kind: Literal['confirmed', 'estimated', 'unknown_time']
    reason: str

class ReminderIn(BaseModel):
    reminder_type: ReminderType
    scheduled_at: datetime | None = None
    delivery_channel: Literal['local', 'push'] = 'local'
    @model_validator(mode='after')
    def custom_date(self):
        if self.reminder_type == 'custom' and (not self.scheduled_at or not self.scheduled_at.tzinfo): raise ValueError('Custom reminder must have a timezone-aware date')
        return self

class ReminderUpdate(BaseModel):
    scheduled_at: datetime | None = None
    status: Literal['pending', 'scheduled_local', 'cancelled'] | None = None

class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; hearing_id: UUID; reminder_type: ReminderType; scheduled_at: datetime
    delivery_channel: str; status: str; sent_at: datetime | None; attempt_count: int
    created_at: datetime; updated_at: datetime

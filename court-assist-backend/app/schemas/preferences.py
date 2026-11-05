from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    timezone: str
    date_format: str
    time_format: str
    theme: str
    hearing_reminders: bool
    task_reminders: bool
    appointment_reminders: bool
    payment_reminders: bool
    daily_summary: bool
    updated_at: datetime


class PreferencesUpdate(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    date_format: str | None = Field(default=None, pattern='^(DD/MM/YYYY|MM/DD/YYYY|YYYY-MM-DD)$')
    time_format: str | None = Field(default=None, pattern='^(12|24)$')
    theme: str | None = Field(default=None, pattern='^(light|dark|system)$')
    hearing_reminders: bool | None = None
    task_reminders: bool | None = None
    appointment_reminders: bool | None = None
    payment_reminders: bool | None = None
    daily_summary: bool | None = None

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError:
                raise ValueError('Invalid timezone') from None
        return value

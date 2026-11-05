from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.preferences import PreferencesOut


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str
    email: str | None
    phone_number: str | None
    profile_image: str | None
    signature_image: str | None
    date_of_birth: date | None
    gender: str | None
    address: str | None
    city: str | None
    district: str | None
    state: str | None
    pin_code: str | None
    enrollment_number: str | None
    bar_council: str | None
    enrollment_date: date | None
    professional_designation: str | None
    years_of_experience: int | None
    office_name: str | None
    office_address: str | None
    office_phone: str | None
    professional_email: str | None
    areas_of_practice: list[str]
    preferred_language: str
    preferences: PreferencesOut | None
    is_email_verified: bool
    is_phone_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone_number: str | None = Field(default=None, max_length=32)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern='^(female|male|non_binary|prefer_not_to_say)$')
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    pin_code: str | None = Field(default=None, pattern=r'^\d{6}$')
    enrollment_number: str | None = Field(default=None, max_length=100)
    bar_council: str | None = Field(default=None, max_length=160)
    enrollment_date: date | None = None
    professional_designation: str | None = Field(default=None, max_length=120)
    years_of_experience: int | None = Field(default=None, ge=0, le=80)
    office_name: str | None = Field(default=None, max_length=160)
    office_address: str | None = Field(default=None, max_length=500)
    office_phone: str | None = Field(default=None, max_length=32)
    professional_email: str | None = Field(default=None, max_length=320)
    areas_of_practice: list[str] | None = Field(default=None, max_length=12)
    preferred_language: str | None = Field(default=None, pattern='^(en|ml)$')

    @field_validator('full_name')
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Full name is required')
        return value

    @field_validator('date_of_birth', 'enrollment_date')
    @classmethod
    def not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError('Date cannot be in the future')
        return value

    @field_validator('areas_of_practice')
    @classmethod
    def clean_areas(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        areas = [item.strip() for item in value]
        if any(not item or len(item) > 80 for item in areas):
            raise ValueError('Each practice area must contain 1–80 characters')
        return list(dict.fromkeys(areas))

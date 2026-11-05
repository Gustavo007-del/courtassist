from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator
from app.schemas.client import clean_phone

class CourtBase(BaseModel):
    name: str = Field(min_length=2, max_length=240)
    court_type: str = Field(min_length=2, max_length=64)
    state: str = Field(min_length=1, max_length=120)
    district: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=2, max_length=500)
    phone_number: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    official_website: HttpUrl | None = Field(default=None, max_length=500)
    jurisdiction: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    source: HttpUrl | None = Field(default=None, max_length=500)

    @field_validator('phone_number')
    @classmethod
    def phone(cls, value): return clean_phone(value)

    @field_validator('name', 'court_type', 'state', 'district', 'address', 'jurisdiction', 'notes', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value


class CourtCreate(CourtBase): pass
class CourtUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=240)
    court_type: str | None = Field(default=None, min_length=2, max_length=64)
    state: str | None = Field(default=None, min_length=1, max_length=120)
    district: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, min_length=2, max_length=500)
    phone_number: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    official_website: HttpUrl | None = Field(default=None, max_length=500)
    jurisdiction: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator('phone_number')
    @classmethod
    def phone(cls, value): return clean_phone(value)

    @field_validator('name', 'court_type', 'state', 'district', 'address', 'jurisdiction', 'notes', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value


class CourtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; court_type: str; state: str; district: str; address: str
    phone_number: str | None; email: str | None; official_website: str | None
    jurisdiction: str | None; notes: str | None; source: str | None; is_active: bool
    record_scope: Literal['shared', 'private']; is_favorite: bool; can_edit: bool
    created_at: datetime; updated_at: datetime


class CourtPage(BaseModel):
    items: list[CourtOut]; total: int; limit: int; offset: int

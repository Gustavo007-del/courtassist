from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def clean_phone(value: str | None) -> str | None:
    if value is None: return None
    value = value.strip()
    digits = ''.join(char for char in value if char.isdigit())
    if not 7 <= len(digits) <= 15 or any(char not in '+0123456789 ()-.' for char in value):
        raise ValueError('Enter a valid international phone number')
    return value


class ClientBase(BaseModel):
    client_type: Literal['individual', 'organization']
    full_name: str = Field(min_length=2, max_length=160)
    organization_name: str | None = Field(default=None, max_length=200)
    phone_number: str = Field(max_length=32)
    alternate_phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str = Field(min_length=2, max_length=500)
    city: str = Field(min_length=1, max_length=120)
    district: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=3, max_length=12, pattern=r'^[A-Za-z0-9 -]+$')
    occupation: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator('phone_number', 'alternate_phone')
    @classmethod
    def phone(cls, value): return clean_phone(value)

    @field_validator('full_name', 'organization_name', 'address', 'city', 'district', 'state', 'postal_code', 'occupation', 'notes', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value

    @model_validator(mode='after')
    def organization_required(self):
        if self.client_type == 'organization' and not self.organization_name:
            raise ValueError('Organization name is required')
        return self


class ClientCreate(ClientBase): pass
class ClientUpdate(BaseModel):
    client_type: Literal['individual', 'organization'] | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    organization_name: str | None = Field(default=None, max_length=200)
    phone_number: str | None = Field(default=None, max_length=32)
    alternate_phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=2, max_length=500)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    district: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, min_length=1, max_length=120)
    postal_code: str | None = Field(default=None, min_length=3, max_length=12, pattern=r'^[A-Za-z0-9 -]+$')
    occupation: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator('phone_number', 'alternate_phone')
    @classmethod
    def phone(cls, value): return clean_phone(value)

    @field_validator('full_name', 'organization_name', 'address', 'city', 'district', 'state', 'postal_code', 'occupation', 'notes', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value


class ClientOut(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; is_archived: bool; created_at: datetime; updated_at: datetime
    associated_case_count: int = 0


class ClientPage(BaseModel):
    items: list[ClientOut]; total: int; limit: int; offset: int


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=10000)

    @field_validator('title', 'content', mode='before')
    @classmethod
    def trim(cls, value): return value.strip()


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, min_length=1, max_length=10000)

    @field_validator('title', 'content', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if value is not None else value


class NoteOut(NoteIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; client_id: UUID; created_at: datetime; updated_at: datetime


class InteractionIn(BaseModel):
    interaction_type: Literal['consultation', 'phone_call', 'meeting', 'email', 'other']
    interaction_date: datetime
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    follow_up_required: bool = False
    follow_up_date: date | None = None

    @field_validator('subject', 'description', mode='before')
    @classmethod
    def trim(cls, value): return value.strip()

    @model_validator(mode='after')
    def follow_up(self):
        if self.follow_up_required and not self.follow_up_date: raise ValueError('Follow-up date is required')
        if not self.follow_up_required: self.follow_up_date = None
        return self


class InteractionUpdate(BaseModel):
    interaction_type: Literal['consultation', 'phone_call', 'meeting', 'email', 'other'] | None = None
    interaction_date: datetime | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    follow_up_required: bool | None = None
    follow_up_date: date | None = None

    @field_validator('subject', 'description', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if value is not None else value


class InteractionOut(InteractionIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; client_id: UUID; created_at: datetime; updated_at: datetime

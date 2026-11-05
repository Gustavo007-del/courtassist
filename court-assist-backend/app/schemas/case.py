from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.schemas.client import clean_phone

Status = Literal['Pending', 'Active', 'In Progress', 'Stayed', 'Disposed', 'Dismissed', 'Withdrawn', 'Settled', 'Transferred', 'Archived']
Priority = Literal['Normal', 'High', 'Urgent']

class CaseFields(BaseModel):
    client_id: UUID | None = None
    court_id: UUID | None = None
    case_title: str = Field(min_length=2, max_length=240)
    case_number: str = Field(min_length=1, max_length=120)
    cnr_number: str | None = Field(default=None, max_length=32)
    case_type: str | None = Field(default=None, max_length=120)
    case_category: str = Field(min_length=2, max_length=80)
    filing_number: str | None = Field(default=None, max_length=120)
    filing_date: date
    registration_date: date | None = None
    case_stage: str | None = Field(default=None, max_length=160)
    description: str = Field(default='', max_length=10000)
    jurisdiction: str | None = Field(default=None, max_length=500)
    judge_name: str | None = Field(default=None, max_length=160)
    courtroom: str | None = Field(default=None, max_length=120)
    priority: Priority = 'Normal'
    is_confidential: bool = False

    @field_validator('case_title', 'case_number', 'cnr_number', 'case_type', 'case_category', 'filing_number', 'case_stage', 'description', 'jurisdiction', 'judge_name', 'courtroom', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value

    @model_validator(mode='after')
    def dates(self):
        if self.registration_date and self.registration_date < self.filing_date: raise ValueError('Registration date cannot precede filing date')
        return self

class PartyFields(BaseModel):
    client_id: UUID | None = None
    party_name: str = Field(min_length=2, max_length=200)
    party_type: Literal['individual', 'organization'] = 'individual'
    party_role: str = Field(min_length=2, max_length=64)
    address: str = Field(default='', max_length=500)
    phone_number: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    description: str | None = Field(default=None, max_length=5000)
    @field_validator('phone_number')
    @classmethod
    def phone(cls, value): return clean_phone(value)
    @field_validator('party_name', 'party_role', 'address', 'description', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value

class AdvocateFields(BaseModel):
    advocate_name: str = Field(min_length=2, max_length=200)
    bar_registration_number: str | None = Field(default=None, max_length=120)
    representation_role: str = Field(min_length=2, max_length=120)
    is_primary: bool = False

class CaseCreate(CaseFields):
    initial_status: Status = 'Pending'
    parties: list[PartyFields] = Field(default_factory=list, max_length=50)
    advocates: list[AdvocateFields] = Field(default_factory=list, max_length=30)

class CaseUpdate(CaseFields):
    client_id: UUID | None = None
    court_id: UUID | None = None
    case_title: str | None = Field(default=None, min_length=2, max_length=240)
    case_number: str | None = Field(default=None, min_length=1, max_length=120)
    case_category: str | None = Field(default=None, min_length=2, max_length=80)
    filing_date: date | None = None
    description: str | None = Field(default=None, max_length=10000)
    priority: Priority | None = None
    is_confidential: bool | None = None
    @model_validator(mode='after')
    def dates(self): return self

    @field_validator('case_title', 'case_number', 'case_category', 'filing_date', 'description', 'priority', 'is_confidential')
    @classmethod
    def required_when_supplied(cls, value):
        if value is None: raise ValueError('This field cannot be null')
        return value

class CaseOut(CaseFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; current_status: Status; is_archived: bool; disposed_at: datetime | None
    created_at: datetime; updated_at: datetime
    court_name: str | None = None; court_district: str | None = None; primary_client_name: str | None = None

class CasePage(BaseModel):
    items: list[CaseOut]; total: int; limit: int; offset: int

class PartyOut(PartyFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; case_id: UUID; created_at: datetime; updated_at: datetime

class AdvocateOut(AdvocateFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; case_id: UUID; created_at: datetime; updated_at: datetime

class StatusChange(BaseModel):
    new_status: Status
    reason: str | None = Field(default=None, max_length=1000)
    effective_date: date

    @field_validator('reason', mode='before')
    @classmethod
    def trim_reason(cls, value): return value.strip() if isinstance(value, str) else value

class StatusOut(StatusChange):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; case_id: UUID; previous_status: Status; created_at: datetime

class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; case_id: UUID; activity_type: str; title: str; description: str | None
    details: dict; created_at: datetime

class ActivityPage(BaseModel):
    items: list[ActivityOut]; total: int; limit: int; offset: int

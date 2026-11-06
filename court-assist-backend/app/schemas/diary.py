from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class DiaryFields(BaseModel):
    case_id: UUID
    hearing_id: UUID | None = None
    entry_date: date
    entry_type: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(default='', max_length=100000)
    proceedings_summary: str | None = Field(default=None, max_length=100000)
    judge_directions: str | None = Field(default=None, max_length=100000)
    arguments_summary: str | None = Field(default=None, max_length=100000)
    evidence_notes: str | None = Field(default=None, max_length=100000)
    witness_notes: str | None = Field(default=None, max_length=100000)
    observations: str | None = Field(default=None, max_length=100000)
    next_action: str | None = Field(default=None, max_length=100000)
    follow_up_date: date | None = None
    is_important: bool = False
    is_pinned: bool = False
    @field_validator('title', 'entry_type', mode='before')
    @classmethod
    def trim(cls, value): return value.strip() if isinstance(value, str) else value

class DiaryCreate(DiaryFields):
    request_id: str | None = Field(default=None, min_length=8, max_length=64)

class DiaryUpdate(BaseModel):
    hearing_id: UUID | None = None
    entry_date: date | None = None
    entry_type: str | None = Field(default=None, min_length=2, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    content: str | None = Field(default=None, max_length=100000)
    proceedings_summary: str | None = Field(default=None, max_length=100000)
    judge_directions: str | None = Field(default=None, max_length=100000)
    arguments_summary: str | None = Field(default=None, max_length=100000)
    evidence_notes: str | None = Field(default=None, max_length=100000)
    witness_notes: str | None = Field(default=None, max_length=100000)
    observations: str | None = Field(default=None, max_length=100000)
    next_action: str | None = Field(default=None, max_length=100000)
    follow_up_date: date | None = None
    is_important: bool | None = None
    is_pinned: bool | None = None

class DiaryOut(DiaryFields):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    case_title: str
    case_number: str
    hearing_date: date | None = None
    created_at: datetime
    updated_at: datetime

class DiaryPage(BaseModel):
    items: list[DiaryOut]
    total: int
    limit: int
    offset: int

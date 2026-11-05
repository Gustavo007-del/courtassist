from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    activity_type: str
    title: str
    description: str | None
    entity_type: str | None
    entity_id: UUID | None
    details: dict
    created_at: datetime


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    limit: int
    offset: int

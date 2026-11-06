from typing import Literal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


Kind = Literal["case", "hearing", "diary", "task", "appointment", "document", "draft", "payment"]
Action = Literal["create", "update", "archive", "delete", "restore", "complete", "reopen", "cancel", "reschedule", "status", "pin", "unpin", "important", "unimportant"]


class Operation(Input):
    id: UUID
    kind: Kind
    entity_id: UUID
    action: Action
    payload: dict = Field(default_factory=dict)
    base_revision: str = Field("0", pattern=r"^\d{1,18}$")
    base_updated_at: datetime | None = None
    local_version: int | None = Field(default=None, ge=1)
    depends_on: list[UUID] = Field(default_factory=list, max_length=25)
    after_operation_id: UUID | None = None


class Push(Input):
    device_id: UUID
    operations: list[Operation] = Field(min_length=1, max_length=20)


class Pull(Input):
    device_id: UUID
    cursor: str = Field("0", pattern=r"^\d{1,18}$")
    limit: int = Field(50, ge=1, le=100)


class Resolution(Input):
    id: UUID
    device_id: UUID
    strategy: Literal["server", "local", "merge"]
    server_revision: str = Field(pattern=r"^\d{1,18}$")
    payload: dict | None = None


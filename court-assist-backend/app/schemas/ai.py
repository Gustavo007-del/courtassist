from datetime import date as CalendarDate, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=8000)]
SourceKind = Literal["case", "document", "diary", "hearing", "timeline", "status", "research", "task"]
Language = Literal["source", "en", "ml"]


class PreferencesPatch(Input):
    enabled: bool = False
    documents: bool = False
    assistant: bool = False
    external: bool = False
    retention_days: int = Field(30, ge=1, le=90)
    external_confirmation: str | None = Field(None, max_length=64)


class SourceSelection(Input):
    kind: SourceKind
    id: UUID
    first_page: int | None = Field(None, ge=1, le=500)
    last_page: int | None = Field(None, ge=1, le=500)

    @model_validator(mode="after")
    def page_range(self):
        if self.first_page is None and self.last_page is None:
            return self
        if self.kind != "document" or not self.first_page or not self.last_page or self.first_page > self.last_page:
            raise ValueError("Provide a valid document page range")
        return self


class Submission(Input):
    request_id: UUID = Field(default_factory=uuid4)
    language: Language = "source"
    external_confirmation: str | None = Field(None, max_length=64)


class ScopedSubmission(Submission):
    sources: list[SourceSelection] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_sources(self):
        if len({(source.kind, source.id) for source in self.sources}) != len(self.sources):
            raise ValueError("Duplicate source selection")
        return self


class Ask(ScopedSubmission):
    case_id: UUID | None = None
    previous_job_id: UUID | None = None
    question: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class Writing(Submission):
    text: ShortText
    action: Literal["improve", "rewrite", "organize", "summarize", "translate", "actions", "chronological"] = "organize"


class DiaryWriting(Writing):
    entry_id: UUID | None = None
    case_id: UUID | None = None


class Evidence(Input):
    source: int = Field(ge=1)
    quote: Annotated[str, StringConstraints(min_length=8, max_length=1200)]
    section: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    date: CalendarDate | None = None
    date_status: Literal["explicit", "inferred", "missing"] = "missing"


class GroundedResponse(Input):
    items: list[Evidence] = Field(max_length=24)


class WritingResponse(Input):
    suggestion: Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class Review(Input):
    text: Annotated[str, StringConstraints(min_length=1, max_length=30000)]


class DraftApproval(Input):
    text: ShortText
    expected_updated_at: datetime
    mode: Literal["append", "replace"] = "append"


class DiaryApproval(Input):
    text: ShortText
    title: Annotated[str, StringConstraints(min_length=1, max_length=240)]
    case_id: UUID
    entry_date: CalendarDate
    item_index: int | None = Field(None, ge=0, le=499)


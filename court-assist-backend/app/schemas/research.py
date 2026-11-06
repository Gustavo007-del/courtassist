from datetime import date
from typing import Annotated, Literal
from uuid import UUID
from pydantic import (
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
    create_model,
)
from app.schemas.practice import Input, patch_schema

ITEM_TYPES = [
    "Judgment",
    "Court order",
    "Act",
    "Section",
    "Rule",
    "Regulation",
    "Legal article",
    "Citation",
    "Precedent",
    "Research note",
    "External reference",
    "Other",
]
Name = Annotated[str, Field(min_length=1, max_length=240)]
TagName = Annotated[str, Field(min_length=1, max_length=80)]


class ResearchInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    title: Name
    item_type: Annotated[str, Field(min_length=1, max_length=60)] = "Research note"
    court: Annotated[str, Field(max_length=180)] = ""
    case_number: Annotated[str, Field(max_length=120)] = ""
    cnr_number: Annotated[str, Field(max_length=32)] = ""
    citation: Annotated[str, Field(max_length=240)] = ""
    case_title: Annotated[str, Field(max_length=240)] = ""
    judgment_date: date | None = None
    source_name: Annotated[str, Field(max_length=240)] = ""
    source_url: Annotated[str, Field(max_length=1000)] = ""
    accessed_date: date | None = None
    source_status: Literal["unverified", "manually_entered"] = "manually_entered"
    summary: Annotated[str, Field(max_length=100000)] = ""
    full_text: Annotated[str, Field(max_length=1000000)] = ""
    language: Annotated[str, Field(min_length=2, max_length=10)] = "en"
    act_name: Annotated[str, Field(max_length=240)] = ""
    section_number: Annotated[str, Field(max_length=240)] = ""
    party_information: Annotated[str, Field(max_length=10000)] = ""
    subject: Annotated[str, Field(max_length=180)] = ""
    notes: Annotated[str, Field(max_length=100000)] = ""
    verification_status: Literal["unverified", "manually_verified"] = "unverified"
    verification_notes: Annotated[str, Field(max_length=10000)] = ""
    page_reference: Annotated[str, Field(max_length=240)] = ""
    paragraph_reference: Annotated[str, Field(max_length=240)] = ""
    case_id: UUID | None = None
    client_id: UUID | None = None
    document_id: UUID | None = None
    favorite: bool = False
    tags: list[TagName] = Field(default_factory=list, max_length=30)

    @field_validator("*", mode="before")
    @classmethod
    def no_null_characters(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Null characters are not permitted")
        return value

    @field_validator("title", "item_type")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("A nonblank value is required")
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value):
        if not value:
            return ""
        parsed = TypeAdapter(HttpUrl).validate_python(value)
        if parsed.username or parsed.password:
            raise ValueError("URLs with credentials are not permitted")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def tag_names(cls, value):
        names = []
        seen = set()
        for tag in value:
            tag = tag.strip()
            if not tag or "\x00" in tag:
                raise ValueError("Tag names cannot be blank or contain null characters")
            if tag.casefold() not in seen:
                names.append(tag)
                seen.add(tag.casefold())
        return names

    @model_validator(mode="after")
    def verification(self):
        if (
            self.verification_status == "manually_verified"
            and len(self.verification_notes.strip()) < 3
        ):
            raise ValueError("Manual verification requires verification notes")
        return self


class VerbatimPatch(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


def partial(name, schema):
    return create_model(
        name,
        __base__=VerbatimPatch,
        **{
            key: (field.annotation | None, None)
            for key, field in schema.model_fields.items()
        },
    )


ResearchPatch = partial("ResearchPatch12", ResearchInput)


class TagInput(Input):
    name: TagName
    _safe = field_validator("name", mode="before")(
        ResearchInput.no_null_characters.__func__
    )


class NoteInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    title: Name
    content: Annotated[str, Field(max_length=200000)] = ""
    quoted_text: Annotated[str, Field(max_length=200000)] = ""
    references: Annotated[str, Field(max_length=20000)] = ""
    item_id: UUID | None = None
    case_id: UUID | None = None
    tags: list[TagName] = Field(default_factory=list, max_length=30)
    pinned: bool = False
    language: Annotated[str, Field(min_length=2, max_length=10)] = "en"
    _tags = field_validator("tags")(ResearchInput.tag_names.__func__)
    _title = field_validator("title")(ResearchInput.not_blank.__func__)
    _safe = field_validator("*", mode="before")(
        ResearchInput.no_null_characters.__func__
    )


NotePatch = partial("ResearchNotePatch", NoteInput)


class CaseLinkInput(Input):
    item_id: UUID


class FavoriteInput(Input):
    favorite: bool


class ImportInput(Input):
    csv_text: Annotated[str, Field(max_length=1000000)] = ""
    batch_id: UUID | None = None
    confirm: bool = False
    allow_duplicates: bool = False


class MetadataChoice(Input):
    field: Annotated[str, Field(max_length=80)]
    source_value: Annotated[str, Field(max_length=10000)]
    value: Annotated[str, Field(max_length=10000)]
    status: Literal["accepted", "edited", "rejected"]


class MetadataReview(Input):
    metadata_id: UUID
    choices: list[MetadataChoice] = Field(min_length=1, max_length=100)

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    Uuid,
    UniqueConstraint,
    Index,
    func,
    literal_column,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


def now():
    return datetime.now(timezone.utc)


class ResearchTag(Base):
    __tablename__ = "research_tags"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    normalized_name: Mapped[str] = mapped_column(String(240))
    __table_args__ = (
        UniqueConstraint(
            "user_id", "normalized_name", name="uq_research_tag_owner_name"
        ),
    )


class ResearchItemTag(Base):
    __tablename__ = "research_item_tags"
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_items.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_tags.id"), primary_key=True, index=True
    )


class ResearchNote(Base):
    __tablename__ = "research_notes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text, default="")
    quoted_text: Mapped[str] = mapped_column(Text, default="")
    references: Mapped[str] = mapped_column(Text, default="")
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("research_items.id")
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    pinned: Mapped[bool] = mapped_column(default=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchNoteTag(Base):
    __tablename__ = "research_note_tags"
    note_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_tags.id"), primary_key=True, index=True
    )


class ResearchCaseLink(Base):
    __tablename__ = "research_case_links"
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_items.id", ondelete="CASCADE"), primary_key=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class ResearchSourceMetadata(Base):
    __tablename__ = "research_source_metadata"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_items.id"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id"))
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document_versions.id")
    )
    ocr_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("document_ocr.id"))
    suggestions: Mapped[list] = mapped_column(JSON, default=list)
    reviewed: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("item_id", "version_id", name="uq_research_source_version"),
    )


class ResearchAudit(Base):
    __tablename__ = "research_audit"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("research_items.id"), index=True
    )
    note_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("research_notes.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResearchImportBatch(Base):
    __tablename__ = "research_import_batches"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    records: Mapped[list] = mapped_column(JSON, default=list)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    imported_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="preview")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


from app.models.phase10 import ResearchItem
from app.services.research_search import SEARCH_COLUMNS

Index("ix_research_owner_updated", ResearchItem.user_id, ResearchItem.updated_at)
Index("ix_research_owner_case", ResearchItem.user_id, ResearchItem.case_id)
Index(
    "ix_research_owner_court_date",
    ResearchItem.user_id,
    ResearchItem.court,
    ResearchItem.judgment_date,
)
Index(
    "ix_research_notes_owner_pinned",
    ResearchNote.user_id,
    ResearchNote.pinned,
    ResearchNote.updated_at,
)
Index("ix_research_notes_owner_case", ResearchNote.user_id, ResearchNote.case_id)
expression = func.coalesce(
    getattr(ResearchItem, SEARCH_COLUMNS[0]), literal_column("''")
)
for name in SEARCH_COLUMNS[1:]:
    expression = expression.op("||")(literal_column("' '")).op("||")(
        func.coalesce(getattr(ResearchItem, name), literal_column("''"))
    )
Index(
    "ix_research_fulltext",
    func.to_tsvector(literal_column("'simple'"), expression),
    postgresql_using="gin",
).ddl_if(dialect="postgresql")

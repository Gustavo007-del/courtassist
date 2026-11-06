"""Private Phase 14 records. Job rows double as a content-free usage ledger after deletion."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class AIPreference(Base):
    __tablename__ = "ai_preferences"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    documents: Mapped[bool] = mapped_column(default=False)
    assistant: Mapped[bool] = mapped_column(default=False)
    external: Mapped[bool] = mapped_column(default=False)
    retention_days: Mapped[int] = mapped_column(default=30)
    revision: Mapped[int] = mapped_column(default=0)
    provider_consent: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (UniqueConstraint("id", "user_id"), Index("ix_ai_conversations_owner_created", "user_id", "created_at"))

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIJob(Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id"),
        UniqueConstraint("id", "user_id"),
        ForeignKeyConstraint(["conversation_id", "user_id"], ["ai_conversations.id", "ai_conversations.user_id"]),
        Index("ix_ai_jobs_owner_created", "user_id", "created_at"),
        Index("ix_ai_jobs_queue", "status", "available_at"),
        Index("ix_ai_jobs_expiry", "expires_at"),
        Index("ix_ai_jobs_document", "user_id", "document_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    request_id: Mapped[UUID] = mapped_column(Uuid)
    request_digest: Mapped[str | None] = mapped_column(String(64))
    conversation_id: Mapped[UUID | None] = mapped_column(Uuid)
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"))
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    draft_id: Mapped[UUID | None] = mapped_column(ForeignKey("draft_documents.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(160))
    provider_fingerprint: Mapped[str] = mapped_column(String(64))
    consent_revision: Mapped[int]
    request_data: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    review: Mapped[dict | None] = mapped_column(JSON)
    approval: Mapped[dict | None] = mapped_column(JSON)
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    estimated_cost: Mapped[float | None]
    attempts: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIChunk(Base):
    __tablename__ = "ai_document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "user_id"], ["ai_jobs.id", "ai_jobs.user_id"], ondelete="CASCADE"),
        UniqueConstraint("job_id", "ordinal"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    page: Mapped[int | None]
    embedding: Mapped[list] = mapped_column(JSON)


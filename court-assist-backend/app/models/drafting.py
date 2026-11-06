import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class DraftExport(Base):
    __tablename__ = "draft_exports"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("draft_documents.id"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id"))
    file_format: Mapped[str] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DraftAudit(Base):
    __tablename__ = "draft_audit"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("draft_documents.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

"""Owner-scoped synchronization records. Feed entries contain identifiers, never record bodies."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now():
    return datetime.now(timezone.utc)


class SyncDevice(Base):
    __tablename__ = "sync_devices"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    cursor: Mapped[int] = mapped_column(BigInteger, default=0)


class SyncChange(Base):
    __tablename__ = "sync_changes"
    __table_args__ = (
        Index("ix_sync_changes_owner_cursor", "user_id", "revision"),
        Index("ix_sync_changes_record_revision", "user_id", "kind", "entity_id", "revision"),
    )

    revision: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    deleted: Mapped[bool] = mapped_column(default=False)


class SyncOperation(Base):
    __tablename__ = "sync_operations"
    __table_args__ = (Index("ix_sync_operations_owner_status", "user_id", "status", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    device_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[UUID] = mapped_column(Uuid)
    digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int | None] = mapped_column(BigInteger)
    request: Mapped[dict | None] = mapped_column(JSON)
    server_record: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(80))
    resolution: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


def utcnow(): return datetime.now(timezone.utc)


class Court(Base):
    __tablename__ = 'courts'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(240))
    court_type: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(500))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    official_website: Mapped[str | None] = mapped_column(String(500))
    jurisdiction: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    favorites: Mapped[list['AdvocateCourtFavorite']] = relationship(back_populates='court', cascade='all, delete-orphan')


class AdvocateCourtFavorite(Base):
    __tablename__ = 'advocate_court_favorites'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    court_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('courts.id', ondelete='CASCADE'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    court: Mapped[Court] = relationship(back_populates='favorites')
    __table_args__ = (UniqueConstraint('user_id', 'court_id', name='uq_favorite_user_court'),)


Index('ix_courts_visibility_location', Court.user_id, Court.is_active, Court.state, Court.district)
Index('ix_courts_name', Court.name)
Index('ix_favorites_user_created', AdvocateCourtFavorite.user_id, AdvocateCourtFavorite.created_at)

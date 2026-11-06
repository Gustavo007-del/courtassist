import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

def utcnow(): return datetime.now(timezone.utc)

class CaseDiaryEntry(Base):
    __tablename__ = 'case_diary_entries'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('hearings.id', ondelete='SET NULL'))
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default='')
    proceedings_summary: Mapped[str | None] = mapped_column(Text)
    judge_directions: Mapped[str | None] = mapped_column(Text)
    arguments_summary: Mapped[str | None] = mapped_column(Text)
    evidence_notes: Mapped[str | None] = mapped_column(Text)
    witness_notes: Mapped[str | None] = mapped_column(Text)
    observations: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    is_important: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    case: Mapped['Case'] = relationship(back_populates='diary_entries')
    hearing: Mapped['Hearing | None'] = relationship(back_populates='diary_entries')
    __table_args__ = (UniqueConstraint('user_id', 'request_id', name='uq_diary_owner_request'),)

Index('ix_diary_owner_case_date', CaseDiaryEntry.user_id, CaseDiaryEntry.case_id, CaseDiaryEntry.entry_date)
Index('ix_diary_owner_date', CaseDiaryEntry.user_id, CaseDiaryEntry.entry_date)
Index('ix_diary_owner_hearing', CaseDiaryEntry.user_id, CaseDiaryEntry.hearing_id)

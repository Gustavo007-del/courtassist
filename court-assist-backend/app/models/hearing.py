import uuid
from datetime import date, datetime, time, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, Time, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

def utcnow(): return datetime.now(timezone.utc)

class Hearing(Base):
    __tablename__ = 'hearings'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    court_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('courts.id', ondelete='SET NULL'))
    hearing_date: Mapped[date] = mapped_column(Date, nullable=False)
    hearing_time: Mapped[time | None] = mapped_column(Time)
    estimated_end_time: Mapped[time | None] = mapped_column(Time)
    hearing_type: Mapped[str] = mapped_column(String(80), nullable=False)
    hearing_stage: Mapped[str | None] = mapped_column(String(160))
    courtroom: Mapped[str | None] = mapped_column(String(120))
    judge_name: Mapped[str | None] = mapped_column(String(160))
    purpose: Mapped[str] = mapped_column(String(1000), nullable=False)
    proceedings_notes: Mapped[str | None] = mapped_column(Text)
    judge_directions: Mapped[str | None] = mapped_column(Text)
    adjournment_reason: Mapped[str | None] = mapped_column(String(1000))
    outcome: Mapped[str | None] = mapped_column(Text)
    next_hearing_date: Mapped[date | None] = mapped_column(Date)
    next_hearing_time: Mapped[time | None] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_hearing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('hearings.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    case: Mapped['Case'] = relationship(foreign_keys=[case_id])
    court: Mapped['Court | None'] = relationship(foreign_keys=[court_id])
    reminders: Mapped[list['HearingReminder']] = relationship(back_populates='hearing', cascade='all, delete-orphan')
    diary_entries: Mapped[list['CaseDiaryEntry']] = relationship(back_populates='hearing')

class HearingReminder(Base):
    __tablename__ = 'hearing_reminders'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    hearing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('hearings.id', ondelete='CASCADE'), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='pending', nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    hearing: Mapped[Hearing] = relationship(back_populates='reminders')
    __table_args__ = (UniqueConstraint('hearing_id', 'reminder_type', 'delivery_channel', name='uq_hearing_reminder_kind_channel'),)

Index('ix_hearings_owner_date_status', Hearing.user_id, Hearing.hearing_date, Hearing.status)
Index('ix_hearings_owner_case_date', Hearing.user_id, Hearing.case_id, Hearing.hearing_date)
Index('ix_reminders_status_due', HearingReminder.status, HearingReminder.scheduled_at)
Index('ix_reminders_owner_hearing', HearingReminder.user_id, HearingReminder.hearing_id)

import uuid
from datetime import date, datetime, time, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Uuid, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    profile_image: Mapped[str | None] = mapped_column(String(500))
    signature_image: Mapped[str | None] = mapped_column(String(500))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    pin_code: Mapped[str | None] = mapped_column(String(6))
    enrollment_number: Mapped[str | None] = mapped_column(String(100))
    bar_council: Mapped[str | None] = mapped_column(String(160))
    enrollment_date: Mapped[date | None] = mapped_column(Date)
    professional_designation: Mapped[str | None] = mapped_column(String(120))
    years_of_experience: Mapped[int | None] = mapped_column(Integer)
    office_name: Mapped[str | None] = mapped_column(String(160))
    office_address: Mapped[str | None] = mapped_column(String(500))
    office_phone: Mapped[str | None] = mapped_column(String(20))
    professional_email: Mapped[str | None] = mapped_column(String(320))
    areas_of_practice: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_language: Mapped[str] = mapped_column(String(2), default='en')
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sessions: Mapped[list['RefreshSession']] = relationship(back_populates='user')
    preferences: Mapped['UserPreference | None'] = relationship(back_populates='user', uselist=False, cascade='all, delete-orphan')


class UserPreference(Base):
    __tablename__ = 'user_preferences'
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Kolkata')
    date_format: Mapped[str] = mapped_column(String(12), default='DD/MM/YYYY')
    time_format: Mapped[str] = mapped_column(String(2), default='12')
    theme: Mapped[str] = mapped_column(String(6), default='system')
    hearing_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    task_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    push_notifications: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    local_notifications: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')
    email_notifications: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    document_reminders: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    draft_reminders: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    hearing_auto_reminders: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    hearing_reminder_days: Mapped[list]=mapped_column(JSON,default=lambda:[1],server_default='[1]')
    reminder_time: Mapped[time]=mapped_column(Time,default=lambda:time(9),server_default='09:00:00')
    daily_summary_time: Mapped[time]=mapped_column(Time,default=lambda:time(8),server_default='08:00:00')
    quiet_start: Mapped[time|None]=mapped_column(Time)
    quiet_end: Mapped[time|None]=mapped_column(Time)
    urgent_quiet_override: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    task_due_today: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    task_overdue_alerts: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    task_high_priority: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    overdue_repeat_days: Mapped[int|None]=mapped_column(Integer)
    payment_due_days: Mapped[int]=mapped_column(Integer,default=1,server_default='1')
    finance_auto_reminders: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    notification_checked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    user: Mapped[User] = relationship(back_populates='preferences')


class RefreshSession(Base):
    __tablename__ = 'refresh_sessions'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates='sessions')


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_tokens'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

Index('ix_refresh_sessions_family_active', RefreshSession.family_id, RefreshSession.revoked_at)
Index('ix_refresh_sessions_owner_family_active', RefreshSession.user_id, RefreshSession.family_id,
      RefreshSession.expires_at, postgresql_where=RefreshSession.revoked_at.is_(None))

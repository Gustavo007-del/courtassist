import uuid
from datetime import date, datetime, time, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Time, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


def utcnow(): return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='', nullable=False)
    category: Mapped[str] = mapped_column(String(80), default='General', nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default='Medium', nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='Pending', nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    due_time: Mapped[time | None] = mapped_column(Time)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='SET NULL'))
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='SET NULL'))
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('hearings.id', ondelete='SET NULL'))
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('documents.id', ondelete='SET NULL'))
    recurrence_kind: Mapped[str] = mapped_column(String(16), default='none', nullable=False)
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    recurrence_root_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('tasks.id', ondelete='SET NULL'))
    occurrence_date: Mapped[date | None] = mapped_column(Date)
    reminder_minutes: Mapped[int | None] = mapped_column(Integer)
    follow_up_notes: Mapped[str] = mapped_column(Text, default='', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('recurrence_root_id', 'occurrence_date', name='uq_task_recurrence_occurrence'),)


class Appointment(Base):
    __tablename__ = 'appointments'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='', nullable=False)
    appointment_type: Mapped[str] = mapped_column(String(80), default='General appointment', nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    location: Mapped[str] = mapped_column(String(500), default='', nullable=False)
    meeting_mode: Mapped[str] = mapped_column(String(24), default='In person', nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='SET NULL'))
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='SET NULL'))
    attendee_details: Mapped[str] = mapped_column(String(500), default='', nullable=False)
    reminder_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='Scheduled', nullable=False)
    private_notes: Mapped[str] = mapped_column(Text, default='', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanningReminder(Base):
    __tablename__ = 'planning_reminders'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('tasks.id', ondelete='CASCADE'))
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('appointments.id', ondelete='CASCADE'))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='pending', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint('task_id', name='uq_task_planning_reminder'), UniqueConstraint('appointment_id', name='uq_appointment_planning_reminder'))


Index('ix_tasks_owner_due', Task.user_id, Task.due_date, Task.status)
Index('ix_tasks_owner_case', Task.user_id, Task.case_id)
Index('ix_tasks_owner_category', Task.user_id, Task.category)
Index('ix_appointments_owner_date', Appointment.user_id, Appointment.appointment_date, Appointment.start_time)
Index('ix_reminders_owner_due', PlanningReminder.user_id, PlanningReminder.scheduled_at)

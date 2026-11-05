import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

def utcnow(): return datetime.now(timezone.utc)

class Case(Base):
    __tablename__ = 'cases'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='SET NULL'))
    court_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('courts.id', ondelete='SET NULL'))
    case_title: Mapped[str] = mapped_column(String(240), nullable=False)
    case_number: Mapped[str] = mapped_column(String(120), nullable=False)
    cnr_number: Mapped[str | None] = mapped_column(String(32))
    case_type: Mapped[str | None] = mapped_column(String(120))
    case_category: Mapped[str] = mapped_column(String(80), nullable=False)
    filing_number: Mapped[str | None] = mapped_column(String(120))
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    registration_date: Mapped[date | None] = mapped_column(Date)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False)
    case_stage: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(500))
    judge_name: Mapped[str | None] = mapped_column(String(160))
    courtroom: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    disposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    primary_client: Mapped['Client | None'] = relationship(foreign_keys=[client_id])
    court: Mapped['Court | None'] = relationship(foreign_keys=[court_id])
    parties: Mapped[list['CaseParty']] = relationship(back_populates='case', cascade='all, delete-orphan')
    advocates: Mapped[list['CaseAdvocate']] = relationship(back_populates='case', cascade='all, delete-orphan')
    status_history: Mapped[list['CaseStatusHistory']] = relationship(back_populates='case', cascade='all, delete-orphan')
    case_activities: Mapped[list['CaseActivity']] = relationship(back_populates='case', cascade='all, delete-orphan')

class CaseParty(Base):
    __tablename__ = 'case_parties'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='SET NULL'))
    party_name: Mapped[str] = mapped_column(String(200), nullable=False)
    party_type: Mapped[str] = mapped_column(String(24), nullable=False)
    party_role: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    case: Mapped[Case] = relationship(back_populates='parties')
    client: Mapped['Client | None'] = relationship(foreign_keys=[client_id])

class CaseAdvocate(Base):
    __tablename__ = 'case_advocates'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    advocate_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bar_registration_number: Mapped[str | None] = mapped_column(String(120))
    representation_role: Mapped[str] = mapped_column(String(120), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    case: Mapped[Case] = relationship(back_populates='advocates')

class CaseStatusHistory(Base):
    __tablename__ = 'case_status_history'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    case: Mapped[Case] = relationship(back_populates='status_history')

class CaseActivity(Base):
    __tablename__ = 'case_activities'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column('metadata', JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    case: Mapped[Case] = relationship(back_populates='case_activities')

Index('ix_cases_owner_archive_updated', Case.user_id, Case.is_archived, Case.updated_at)
Index('ix_cases_owner_status_priority', Case.user_id, Case.current_status, Case.priority)
Index('ix_cases_owner_title', Case.user_id, Case.case_title)
Index('ix_cases_court_filing', Case.court_id, Case.filing_date)
Index('ix_case_parties_owner_case', CaseParty.user_id, CaseParty.case_id)
Index('ix_case_parties_client', CaseParty.client_id)
Index('ix_case_advocates_owner_case', CaseAdvocate.user_id, CaseAdvocate.case_id)
Index('ix_case_status_owner_case_created', CaseStatusHistory.user_id, CaseStatusHistory.case_id, CaseStatusHistory.created_at)
Index('ix_case_activities_owner_case_created', CaseActivity.user_id, CaseActivity.case_id, CaseActivity.created_at)

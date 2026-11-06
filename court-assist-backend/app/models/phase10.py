import uuid
from datetime import datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

def now(): return datetime.now(timezone.utc)

class DraftTemplate(Base):
    __tablename__='draft_templates'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    name: Mapped[str]=mapped_column(String(180),nullable=False)
    category: Mapped[str]=mapped_column(String(80),default='Other')
    description: Mapped[str]=mapped_column(Text,default='')
    content: Mapped[str]=mapped_column(Text,default='')
    active: Mapped[bool]=mapped_column(default=True)
    version: Mapped[int]=mapped_column(Integer,default=1)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class DraftDocument(Base):
    __tablename__='draft_documents'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    template_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('draft_templates.id',ondelete='SET NULL'))
    case_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('cases.id',ondelete='SET NULL'))
    client_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('clients.id',ondelete='SET NULL'))
    title: Mapped[str]=mapped_column(String(240),nullable=False)
    content: Mapped[str]=mapped_column(Text,default='')
    status: Mapped[str]=mapped_column(String(24),default='draft')
    category: Mapped[str]=mapped_column(String(80),default='General legal documents',server_default='General legal documents')
    language: Mapped[str]=mapped_column(String(2),default='en',server_default='en')
    archived_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    last_exported_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class DraftVersion(Base):
    __tablename__='draft_versions'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    document_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('draft_documents.id',ondelete='CASCADE'),index=True)
    user_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    version_number: Mapped[int|None]=mapped_column(Integer)
    content: Mapped[str]=mapped_column(Text,nullable=False)
    description: Mapped[str]=mapped_column(String(240),default='Saved version')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class DraftClause(Base):
    __tablename__='draft_clauses'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    title: Mapped[str]=mapped_column(String(180),nullable=False)
    category: Mapped[str]=mapped_column(String(80),default='General')
    content: Mapped[str]=mapped_column(Text,nullable=False)
    tags: Mapped[list]=mapped_column(JSON,default=list)

class FeeAgreement(Base):
    __tablename__='fee_agreements'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    client_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('clients.id'),index=True)
    case_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('cases.id',ondelete='SET NULL'))
    amount: Mapped[object]=mapped_column(Numeric(14,2),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),default='INR')
    fee_type: Mapped[str]=mapped_column(String(40),default='fixed')
    title: Mapped[str]=mapped_column(String(180),default='',server_default='')
    payment_terms: Mapped[str]=mapped_column(Text,default='',server_default='')
    notes: Mapped[str]=mapped_column(Text,default='',server_default='')
    updated_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    description: Mapped[str]=mapped_column(Text,default='')
    agreement_date: Mapped[datetime|None]=mapped_column(Date)
    due_date: Mapped[datetime|None]=mapped_column(Date)
    status: Mapped[str]=mapped_column(String(24),default='active')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Payment(Base):
    __tablename__='payments'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    client_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('clients.id'),index=True)
    case_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('cases.id',ondelete='SET NULL'))
    agreement_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('fee_agreements.id',ondelete='SET NULL'))
    amount: Mapped[object]=mapped_column(Numeric(14,2),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),default='INR')
    payment_date: Mapped[datetime]=mapped_column(Date,nullable=False)
    method: Mapped[str]=mapped_column(String(40),default='UPI')
    status: Mapped[str]=mapped_column(String(24),default='pending')
    reference: Mapped[str]=mapped_column(String(120),default='')
    description: Mapped[str]=mapped_column(Text,default='',server_default='')
    notes: Mapped[str]=mapped_column(Text,default='',server_default='')
    receipt_number: Mapped[str|None]=mapped_column(String(60))
    updated_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    idempotency_key: Mapped[str|None]=mapped_column(String(100))
    request_digest: Mapped[str|None]=mapped_column(String(64))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Expense(Base):
    __tablename__='expenses'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    client_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('clients.id',ondelete='SET NULL'))
    case_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('cases.id',ondelete='SET NULL'))
    amount: Mapped[object]=mapped_column(Numeric(14,2),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),default='INR')
    category: Mapped[str]=mapped_column(String(80),default='Other')
    description: Mapped[str]=mapped_column(Text,default='')
    payment_method: Mapped[str]=mapped_column(String(40),default='Cash',server_default='Cash')
    vendor: Mapped[str]=mapped_column(String(180),default='',server_default='')
    reference: Mapped[str]=mapped_column(String(120),default='',server_default='')
    notes: Mapped[str]=mapped_column(Text,default='',server_default='')
    document_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('documents.id',name='fk_expense_document'))
    status: Mapped[str]=mapped_column(String(20),default='confirmed',server_default='confirmed')
    archived_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    expense_date: Mapped[datetime]=mapped_column(Date,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ResearchItem(Base):
    __tablename__='research_items'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    case_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('cases.id',ondelete='SET NULL'))
    title: Mapped[str]=mapped_column(String(240),nullable=False)
    item_type: Mapped[str]=mapped_column(String(60),default='note')
    citation: Mapped[str]=mapped_column(String(240),default='')
    court: Mapped[str]=mapped_column(String(180),default='')
    subject: Mapped[str]=mapped_column(String(180),default='')
    source_url: Mapped[str]=mapped_column(String(1000),default='')
    source_status: Mapped[str]=mapped_column(String(30),default='unverified')
    summary: Mapped[str]=mapped_column(Text,default='')
    notes: Mapped[str]=mapped_column(Text,default='')
    tags: Mapped[list]=mapped_column(JSON,default=list)
    case_number: Mapped[str]=mapped_column(String(120),default='',server_default='')
    cnr_number: Mapped[str]=mapped_column(String(32),default='',server_default='')
    case_title: Mapped[str]=mapped_column(String(240),default='',server_default='')
    judgment_date: Mapped[datetime|None]=mapped_column(Date)
    source_name: Mapped[str]=mapped_column(String(240),default='',server_default='')
    accessed_date: Mapped[datetime|None]=mapped_column(Date)
    full_text: Mapped[str]=mapped_column(Text,default='',server_default='')
    language: Mapped[str]=mapped_column(String(10),default='en',server_default='en')
    act_name: Mapped[str]=mapped_column(String(240),default='',server_default='')
    section_number: Mapped[str]=mapped_column(String(240),default='',server_default='')
    party_information: Mapped[str]=mapped_column(Text,default='',server_default='')
    verification_status: Mapped[str]=mapped_column(String(30),default='unverified',server_default='unverified')
    verification_notes: Mapped[str]=mapped_column(Text,default='',server_default='')
    page_reference: Mapped[str]=mapped_column(String(240),default='',server_default='')
    paragraph_reference: Mapped[str]=mapped_column(String(240),default='',server_default='')
    client_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('clients.id',name='fk_research_client'))
    document_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('documents.id',name='fk_research_document'))
    favorite: Mapped[bool]=mapped_column(default=False,server_default='false')
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    archived_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

Index('uq_payment_idempotency',Payment.user_id,Payment.idempotency_key,unique=True)
Index('ix_research_owner_type',ResearchItem.user_id,ResearchItem.item_type)

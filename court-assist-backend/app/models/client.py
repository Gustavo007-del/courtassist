import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


def utcnow(): return datetime.now(timezone.utc)


class Client(Base):
    __tablename__ = 'clients'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    client_type: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(160))
    organization_name: Mapped[str | None] = mapped_column(String(200))
    phone_number: Mapped[str] = mapped_column(String(32))
    alternate_phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120))
    postal_code: Mapped[str] = mapped_column(String(12))
    occupation: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_notes: Mapped[list['ClientNote']] = relationship(back_populates='client', cascade='all, delete-orphan')
    interactions: Mapped[list['ClientInteraction']] = relationship(back_populates='client', cascade='all, delete-orphan')


class ClientNote(Base):
    __tablename__ = 'client_notes'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    client: Mapped[Client] = relationship(back_populates='client_notes')


class ClientInteraction(Base):
    __tablename__ = 'client_interactions'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(24))
    interaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    client: Mapped[Client] = relationship(back_populates='interactions')


Index('ix_clients_owner_status_updated', Client.user_id, Client.deleted_at, Client.is_archived, Client.updated_at)
Index('ix_clients_owner_name', Client.user_id, Client.full_name)
Index('ix_client_notes_owner_client_created', ClientNote.user_id, ClientNote.client_id, ClientNote.created_at)
Index('ix_client_interactions_owner_client_date', ClientInteraction.user_id, ClientInteraction.client_id, ClientInteraction.interaction_date)

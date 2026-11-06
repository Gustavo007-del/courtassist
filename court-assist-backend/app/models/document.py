import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('cases.id', ondelete='SET NULL'))
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('clients.id', ondelete='SET NULL'))
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('hearings.id', ondelete='SET NULL'))
    document_name: Mapped[str] = mapped_column(String(240), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(240), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(12), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    document_category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='', nullable=False)
    reviewed_metadata: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(32), default='s3', nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(240), unique=True)
    storage_status: Mapped[str] = mapped_column(String(24), default='upload_pending', nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upload_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    versions: Mapped[list['DocumentVersion']] = relationship(back_populates='document', cascade='all, delete-orphan', foreign_keys='DocumentVersion.document_id')
    ocr_results: Mapped[list['DocumentOCR']] = relationship(back_populates='document', cascade='all, delete-orphan')


class DocumentVersion(Base):
    __tablename__ = 'document_versions'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(240), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(240), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    change_description: Mapped[str] = mapped_column(String(500), default='', nullable=False)
    storage_status: Mapped[str] = mapped_column(String(24), default='upload_pending', nullable=False)
    upload_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    document: Mapped[Document] = relationship(back_populates='versions', foreign_keys=[document_id])
    __table_args__ = (UniqueConstraint('document_id', 'version_number', name='uq_document_version_number'),)


class DocumentOCR(Base):
    __tablename__ = 'document_ocr'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('document_versions.id', ondelete='CASCADE'), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, default='', nullable=False)
    language_detected: Mapped[str | None] = mapped_column(String(80))
    processing_status: Mapped[str] = mapped_column(String(24), default='pending', nullable=False)
    processing_provider: Mapped[str] = mapped_column(String(40), default='pypdf', nullable=False)
    confidence_score: Mapped[float | None] = mapped_column()
    page_results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(300))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    document: Mapped[Document] = relationship(back_populates='ocr_results')
    __table_args__ = (UniqueConstraint('document_version_id', name='uq_ocr_version'),)


class DocumentAccessLog(Base):
    __tablename__ = 'document_access_logs'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


Index('ix_documents_owner_created', Document.user_id, Document.created_at)
Index('ix_documents_owner_case', Document.user_id, Document.case_id)
Index('ix_documents_owner_client', Document.user_id, Document.client_id)
Index('ix_documents_owner_hearing', Document.user_id, Document.hearing_id)
Index('ix_documents_owner_status', Document.user_id, Document.storage_status)
Index('ix_document_ocr_owner_status', DocumentOCR.user_id, DocumentOCR.processing_status)

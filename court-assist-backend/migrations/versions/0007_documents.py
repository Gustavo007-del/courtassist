"""Private document vault, versions, OCR and access audit.

Revision ID: 0007_documents
Revises: 0006_case_diary
"""
from alembic import op
from sqlalchemy import text
from app.models.document import Document, DocumentVersion, DocumentOCR, DocumentAccessLog

revision = '0007_documents'
down_revision = '0006_case_diary'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for model in (Document, DocumentVersion, DocumentOCR, DocumentAccessLog):
        model.__table__.create(bind, checkfirst=True)
    for model in (Document, DocumentVersion, DocumentOCR, DocumentAccessLog):
        for index in model.__table__.indexes:
            index.create(bind, checkfirst=True)
    if bind.dialect.name == 'postgresql':
        bind.execute(text("CREATE INDEX IF NOT EXISTS ix_document_ocr_fts ON document_ocr USING gin (to_tsvector('simple', extracted_text))"))


def downgrade():
    bind = op.get_bind()
    for model in (DocumentAccessLog, DocumentOCR, DocumentVersion, Document):
        model.__table__.drop(bind, checkfirst=True)

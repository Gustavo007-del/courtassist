"""Extend existing drafting records without replacing tables."""
from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Uuid, inspect, text

revision='0010_drafting'
down_revision='0009_phase10'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    columns={c['name'] for c in inspect(bind).get_columns('draft_documents')}
    for column in (Column('category',String(80),nullable=False,server_default='General legal documents'),Column('language',String(2),nullable=False,server_default='en'),Column('archived_at',DateTime(timezone=True)),Column('last_exported_at',DateTime(timezone=True))):
        if column.name not in columns:op.add_column('draft_documents',column)
    columns={c['name'] for c in inspect(bind).get_columns('draft_versions')}
    if 'user_id' not in columns:op.add_column('draft_versions',Column('user_id',Uuid,ForeignKey('users.id',ondelete='CASCADE')))
    if 'version_number' not in columns:op.add_column('draft_versions',Column('version_number',Integer))
    bind.execute(text('UPDATE draft_versions SET user_id = (SELECT user_id FROM draft_documents WHERE draft_documents.id = draft_versions.document_id) WHERE user_id IS NULL'))
    bind.execute(text('UPDATE draft_versions SET version_number = (SELECT COUNT(*) FROM draft_versions AS previous WHERE previous.document_id = draft_versions.document_id AND (previous.created_at < draft_versions.created_at OR (previous.created_at = draft_versions.created_at AND previous.id <= draft_versions.id))) WHERE version_number IS NULL'))

def downgrade():
    for name in ('version_number','user_id'):op.drop_column('draft_versions',name)
    for name in ('last_exported_at','archived_at','language','category'):op.drop_column('draft_documents',name)

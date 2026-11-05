"""Client management and court directory.

Revision ID: 0003_clients_courts
Revises: 0002_workspace
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_clients_courts'
down_revision = '0002_workspace'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('clients',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_type', sa.String(20), nullable=False), sa.Column('full_name', sa.String(160), nullable=False),
        sa.Column('organization_name', sa.String(200)), sa.Column('phone_number', sa.String(32), nullable=False),
        sa.Column('alternate_phone', sa.String(32)), sa.Column('email', sa.String(320)), sa.Column('address', sa.String(500), nullable=False),
        sa.Column('city', sa.String(120), nullable=False), sa.Column('district', sa.String(120), nullable=False),
        sa.Column('state', sa.String(120), nullable=False), sa.Column('postal_code', sa.String(12), nullable=False),
        sa.Column('occupation', sa.String(160)), sa.Column('notes', sa.Text()), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False), sa.Column('is_archived', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True)))
    op.create_index('ix_clients_owner_status_updated', 'clients', ['user_id', 'deleted_at', 'is_archived', 'updated_at'])
    op.create_index('ix_clients_owner_name', 'clients', ['user_id', 'full_name'])
    op.create_table('client_notes',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('client_id', sa.Uuid(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('title', sa.String(160), nullable=False),
        sa.Column('content', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_client_notes_owner_client_created', 'client_notes', ['user_id', 'client_id', 'created_at'])
    op.create_table('client_interactions',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('client_id', sa.Uuid(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('interaction_type', sa.String(24), nullable=False),
        sa.Column('interaction_date', sa.DateTime(timezone=True), nullable=False), sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False), sa.Column('follow_up_required', sa.Boolean(), nullable=False),
        sa.Column('follow_up_date', sa.Date()), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_client_interactions_owner_client_date', 'client_interactions', ['user_id', 'client_id', 'interaction_date'])
    op.create_table('courts',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('name', sa.String(240), nullable=False), sa.Column('court_type', sa.String(64), nullable=False),
        sa.Column('state', sa.String(120), nullable=False), sa.Column('district', sa.String(120), nullable=False),
        sa.Column('address', sa.String(500), nullable=False), sa.Column('phone_number', sa.String(32)), sa.Column('email', sa.String(320)),
        sa.Column('official_website', sa.String(500)), sa.Column('jurisdiction', sa.String(500)), sa.Column('notes', sa.Text()),
        sa.Column('source', sa.String(500)), sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_courts_visibility_location', 'courts', ['user_id', 'is_active', 'state', 'district'])
    op.create_index('ix_courts_name', 'courts', ['name'])
    op.create_table('advocate_court_favorites',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('court_id', sa.Uuid(), sa.ForeignKey('courts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint('user_id', 'court_id', name='uq_favorite_user_court'))
    op.create_index('ix_favorites_user_created', 'advocate_court_favorites', ['user_id', 'created_at'])


def downgrade():
    op.drop_table('advocate_court_favorites'); op.drop_table('courts'); op.drop_table('client_interactions'); op.drop_table('client_notes'); op.drop_table('clients')

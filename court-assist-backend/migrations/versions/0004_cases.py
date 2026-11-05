"""Complete case management. Revision ID: 0004_cases. Revises: 0003_clients_courts."""
from alembic import op
import sqlalchemy as sa

revision = '0004_cases'
down_revision = '0003_clients_courts'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('cases',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.Uuid(), sa.ForeignKey('clients.id', ondelete='SET NULL')), sa.Column('court_id', sa.Uuid(), sa.ForeignKey('courts.id', ondelete='SET NULL')),
        sa.Column('case_title', sa.String(240), nullable=False), sa.Column('case_number', sa.String(120), nullable=False), sa.Column('cnr_number', sa.String(32)),
        sa.Column('case_type', sa.String(120)), sa.Column('case_category', sa.String(80), nullable=False), sa.Column('filing_number', sa.String(120)),
        sa.Column('filing_date', sa.Date(), nullable=False), sa.Column('registration_date', sa.Date()), sa.Column('current_status', sa.String(32), nullable=False),
        sa.Column('case_stage', sa.String(160)), sa.Column('description', sa.Text(), nullable=False), sa.Column('jurisdiction', sa.String(500)),
        sa.Column('judge_name', sa.String(160)), sa.Column('courtroom', sa.String(120)), sa.Column('priority', sa.String(16), nullable=False),
        sa.Column('is_confidential', sa.Boolean(), nullable=False), sa.Column('is_archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('disposed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_cases_owner_archive_updated', 'cases', ['user_id', 'is_archived', 'updated_at'])
    op.create_index('ix_cases_owner_status_priority', 'cases', ['user_id', 'current_status', 'priority'])
    op.create_index('ix_cases_owner_title', 'cases', ['user_id', 'case_title'])
    op.create_index('ix_cases_court_filing', 'cases', ['court_id', 'filing_date'])
    op.create_table('case_parties',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.Uuid(), sa.ForeignKey('clients.id', ondelete='SET NULL')),
        sa.Column('party_name', sa.String(200), nullable=False), sa.Column('party_type', sa.String(24), nullable=False),
        sa.Column('party_role', sa.String(64), nullable=False), sa.Column('address', sa.String(500), nullable=False),
        sa.Column('phone_number', sa.String(32)), sa.Column('email', sa.String(320)), sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_case_parties_owner_case', 'case_parties', ['user_id', 'case_id'])
    op.create_index('ix_case_parties_client', 'case_parties', ['client_id'])
    op.create_table('case_advocates',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('advocate_name', sa.String(200), nullable=False), sa.Column('bar_registration_number', sa.String(120)),
        sa.Column('representation_role', sa.String(120), nullable=False), sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_case_advocates_owner_case', 'case_advocates', ['user_id', 'case_id'])
    op.create_table('case_status_history',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('previous_status', sa.String(32), nullable=False), sa.Column('new_status', sa.String(32), nullable=False),
        sa.Column('reason', sa.String(1000)), sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_case_status_owner_case_created', 'case_status_history', ['user_id', 'case_id', 'created_at'])
    op.create_table('case_activities',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('activity_type', sa.String(64), nullable=False), sa.Column('title', sa.String(160), nullable=False),
        sa.Column('description', sa.String(500)), sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_case_activities_owner_case_created', 'case_activities', ['user_id', 'case_id', 'created_at'])

def downgrade():
    op.drop_table('case_activities')
    op.drop_table('case_status_history')
    op.drop_table('case_advocates')
    op.drop_table('case_parties')
    op.drop_table('cases')

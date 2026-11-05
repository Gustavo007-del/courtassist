"""Private case diary. Revision ID: 0006_case_diary. Revises: 0005_hearings."""
from alembic import op
import sqlalchemy as sa

revision = '0006_case_diary'
down_revision = '0005_hearings'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('case_diary_entries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hearing_id', sa.Uuid(), sa.ForeignKey('hearings.id', ondelete='SET NULL')),
        sa.Column('entry_date', sa.Date(), nullable=False), sa.Column('entry_type', sa.String(80), nullable=False),
        sa.Column('title', sa.String(240), nullable=False), sa.Column('content', sa.Text(), nullable=False),
        sa.Column('proceedings_summary', sa.Text()), sa.Column('judge_directions', sa.Text()),
        sa.Column('arguments_summary', sa.Text()), sa.Column('evidence_notes', sa.Text()),
        sa.Column('witness_notes', sa.Text()), sa.Column('observations', sa.Text()),
        sa.Column('next_action', sa.Text()), sa.Column('follow_up_date', sa.Date()),
        sa.Column('is_important', sa.Boolean(), nullable=False), sa.Column('is_pinned', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_diary_owner_case_date', 'case_diary_entries', ['user_id', 'case_id', 'entry_date'])
    op.create_index('ix_diary_owner_date', 'case_diary_entries', ['user_id', 'entry_date'])
    op.create_index('ix_diary_owner_hearing', 'case_diary_entries', ['user_id', 'hearing_id'])

def downgrade():
    op.drop_table('case_diary_entries')

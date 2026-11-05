"""Hearings and reminders. Revision ID: 0005_hearings. Revises: 0004_cases."""
from alembic import op
import sqlalchemy as sa

revision = '0005_hearings'
down_revision = '0004_cases'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('hearings',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('court_id', sa.Uuid(), sa.ForeignKey('courts.id', ondelete='SET NULL')),
        sa.Column('hearing_date', sa.Date(), nullable=False), sa.Column('hearing_time', sa.Time()), sa.Column('estimated_end_time', sa.Time()),
        sa.Column('hearing_type', sa.String(80), nullable=False), sa.Column('hearing_stage', sa.String(160)),
        sa.Column('courtroom', sa.String(120)), sa.Column('judge_name', sa.String(160)), sa.Column('purpose', sa.String(1000), nullable=False),
        sa.Column('proceedings_notes', sa.Text()), sa.Column('judge_directions', sa.Text()), sa.Column('adjournment_reason', sa.String(1000)),
        sa.Column('outcome', sa.Text()), sa.Column('next_hearing_date', sa.Date()), sa.Column('next_hearing_time', sa.Time()),
        sa.Column('status', sa.String(32), nullable=False), sa.Column('reminder_enabled', sa.Boolean(), nullable=False),
        sa.Column('follow_up_hearing_id', sa.Uuid(), sa.ForeignKey('hearings.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_hearings_owner_date_status', 'hearings', ['user_id', 'hearing_date', 'status'])
    op.create_index('ix_hearings_owner_case_date', 'hearings', ['user_id', 'case_id', 'hearing_date'])
    op.create_table('hearing_reminders',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hearing_id', sa.Uuid(), sa.ForeignKey('hearings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reminder_type', sa.String(32), nullable=False), sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivery_channel', sa.String(16), nullable=False), sa.Column('status', sa.String(24), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True)), sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(500)), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('hearing_id', 'reminder_type', 'delivery_channel', name='uq_hearing_reminder_kind_channel'))
    op.create_index('ix_reminders_status_due', 'hearing_reminders', ['status', 'scheduled_at'])
    op.create_index('ix_reminders_owner_hearing', 'hearing_reminders', ['user_id', 'hearing_id'])

def downgrade():
    op.drop_table('hearing_reminders')
    op.drop_table('hearings')

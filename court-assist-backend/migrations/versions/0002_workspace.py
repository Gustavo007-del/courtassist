"""Advocate profile, preferences, activity and private image uploads.

Revision ID: 0002_workspace
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_workspace'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    fields = [
        sa.Column('signature_image', sa.String(500)),
        sa.Column('date_of_birth', sa.Date()),
        sa.Column('gender', sa.String(32)),
        sa.Column('address', sa.String(500)),
        sa.Column('city', sa.String(120)),
        sa.Column('district', sa.String(120)),
        sa.Column('state', sa.String(120)),
        sa.Column('pin_code', sa.String(6)),
        sa.Column('enrollment_date', sa.Date()),
        sa.Column('professional_designation', sa.String(120)),
        sa.Column('years_of_experience', sa.Integer()),
        sa.Column('office_name', sa.String(160)),
        sa.Column('office_phone', sa.String(20)),
        sa.Column('professional_email', sa.String(320)),
        sa.Column('areas_of_practice', sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    ]
    for field in fields:
        op.add_column('users', field)

    op.create_table('user_preferences',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('timezone', sa.String(64), nullable=False),
        sa.Column('date_format', sa.String(12), nullable=False),
        sa.Column('time_format', sa.String(2), nullable=False),
        sa.Column('theme', sa.String(6), nullable=False),
        sa.Column('hearing_reminders', sa.Boolean(), nullable=False),
        sa.Column('task_reminders', sa.Boolean(), nullable=False),
        sa.Column('appointment_reminders', sa.Boolean(), nullable=False),
        sa.Column('payment_reminders', sa.Boolean(), nullable=False),
        sa.Column('daily_summary', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.execute("""INSERT INTO user_preferences
        (user_id, timezone, date_format, time_format, theme, hearing_reminders,
         task_reminders, appointment_reminders, payment_reminders, daily_summary, updated_at)
        SELECT id, 'Asia/Kolkata', 'DD/MM/YYYY', '12', 'system', true, true, true, true, false, CURRENT_TIMESTAMP
        FROM users""")

    op.create_table('activities',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('activity_type', sa.String(64), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('entity_type', sa.String(64)),
        sa.Column('entity_id', sa.Uuid()),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_activities_user_created', 'activities', ['user_id', 'created_at', 'id'])
    op.create_index('ix_activities_user_type_created', 'activities', ['user_id', 'activity_type', 'created_at'])

    op.create_table('image_uploads',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('purpose', sa.String(24), nullable=False),
        sa.Column('content_type', sa.String(32), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_image_uploads_user_id', 'image_uploads', ['user_id'])


def downgrade():
    op.drop_table('image_uploads')
    op.drop_table('activities')
    op.drop_table('user_preferences')
    for name in ('areas_of_practice', 'professional_email', 'office_phone', 'office_name',
                 'years_of_experience', 'professional_designation', 'enrollment_date',
                 'pin_code', 'state', 'district', 'city', 'address', 'gender',
                 'date_of_birth', 'signature_image'):
        op.drop_column('users', name)

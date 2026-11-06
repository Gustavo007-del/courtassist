"""Tasks, appointments and private reminders.

Revision ID: 0008_planning
Revises: 0007_documents
"""
from alembic import op
from app.models.planning import Task, Appointment, PlanningReminder

revision = '0008_planning'
down_revision = '0007_documents'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for model in (Task, Appointment, PlanningReminder):
        model.__table__.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    for model in (PlanningReminder, Appointment, Task):
        model.__table__.drop(bind, checkfirst=True)

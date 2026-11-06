"""Add private, opt-in AI workspace storage."""

from alembic import op

from app.models.ai import AIChunk, AIConversation, AIJob, AIPreference

revision = "0019_optional_ai"
down_revision = "0018_notifications"
branch_labels = None
depends_on = None


def upgrade():
    for model in (AIPreference, AIConversation, AIJob, AIChunk):
        model.__table__.create(op.get_bind())


def downgrade():
    for model in (AIChunk, AIJob, AIConversation, AIPreference):
        model.__table__.drop(op.get_bind())


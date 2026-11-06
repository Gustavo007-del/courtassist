"""Add durable sync receipts and a commit-ordered record feed."""

from alembic import op
from sqlalchemy import text

from app.models.sync import SyncChange, SyncDevice, SyncOperation
from app.services.sync_feed import MODELS, bootstrap, install_triggers

revision = "0020_offline_sync"
down_revision = "0019_optional_ai"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Block concurrent writes through the backfill and trigger installation.
        tables = ", ".join(model.__tablename__ for model in MODELS.values())
        connection.execute(text(f"LOCK TABLE {tables} IN SHARE ROW EXCLUSIVE MODE"))
    for model in (SyncDevice, SyncChange, SyncOperation):
        model.__table__.create(connection)
    bootstrap(connection)
    install_triggers(connection)


def downgrade():
    connection = op.get_bind()
    for model in MODELS.values():
        table = model.__tablename__
        if connection.dialect.name == "postgresql":
            connection.execute(text(f"DROP TRIGGER ca_sync_{table} ON {table}"))
        elif connection.dialect.name == "sqlite":
            for action in ("insert", "update", "delete"):
                connection.execute(text(f"DROP TRIGGER ca_sync_{table}_{action}"))
    if connection.dialect.name == "postgresql":
        connection.execute(text("DROP FUNCTION ca_capture_sync_change()"))
    for model in (SyncOperation, SyncChange, SyncDevice):
        model.__table__.drop(connection)


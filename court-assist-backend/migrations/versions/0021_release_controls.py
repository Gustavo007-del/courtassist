"""Add account erasure receipts and an owner-scoped session lookup index."""

from alembic import op
import sqlalchemy as sa

revision = "0021_release_controls"
down_revision = "0020_offline_sync"
branch_labels = None
depends_on = None


def upgrade():
    # The original payment migration builds from metadata on clean installs.
    op.add_column('payments', sa.Column('request_digest', sa.String(64)), if_not_exists=True)
    op.create_table(
        "account_erasures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), unique=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_sessions_owner_family_active", "refresh_sessions",
                    ["user_id", "family_id", "expires_at"], postgresql_where=sa.text("revoked_at IS NULL"))


def downgrade():
    op.drop_index("ix_refresh_sessions_owner_family_active", table_name="refresh_sessions")
    op.drop_table("account_erasures")
    op.drop_column('payments', 'request_digest')


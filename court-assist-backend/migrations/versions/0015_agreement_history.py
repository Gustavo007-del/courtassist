"""Explicit fee agreement changes retain the prior record."""
from alembic import op
from app.models.finance import AgreementHistory
revision='0015_agreement_history'
down_revision='0014_draft_skeletons'
branch_labels=None
depends_on=None
def upgrade():AgreementHistory.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():AgreementHistory.__table__.drop(op.get_bind(),checkfirst=True)

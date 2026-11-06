"""Preserve financial corrections as append-only records."""
from alembic import op
from app.models.finance import FinancialAdjustment
revision='0011_financial_adjustments'
down_revision='0010_drafting'
branch_labels=None
depends_on=None

def upgrade():FinancialAdjustment.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():FinancialAdjustment.__table__.drop(op.get_bind(),checkfirst=True)

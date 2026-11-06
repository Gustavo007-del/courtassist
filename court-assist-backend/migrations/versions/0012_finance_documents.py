"""Private, historical invoices and receipts."""
from alembic import op
from app.models.finance import Invoice, Receipt
revision='0012_finance_documents'
down_revision='0011_financial_adjustments'
branch_labels=None
depends_on=None
def upgrade():
    for model in (Invoice,Receipt):model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    for model in (Receipt,Invoice):model.__table__.drop(op.get_bind(),checkfirst=True)

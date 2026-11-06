"""Draft export history and operation audit."""
from alembic import op
from app.models.drafting import DraftExport, DraftAudit
revision='0013_draft_exports'
down_revision='0012_finance_documents'
branch_labels=None
depends_on=None
def upgrade():
    for model in (DraftExport,DraftAudit):model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    for model in (DraftAudit,DraftExport):model.__table__.drop(op.get_bind(),checkfirst=True)

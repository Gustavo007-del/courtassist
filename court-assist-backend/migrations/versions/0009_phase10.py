"""Drafting, finance, and research records.

Revision ID: 0009_phase10
Revises: 0008_planning
"""
from alembic import op
from app.models.phase10 import DraftTemplate, DraftDocument, DraftVersion, DraftClause, FeeAgreement, Payment, Expense, ResearchItem

revision = '0009_phase10'
down_revision = '0008_planning'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    for model in (DraftTemplate, DraftDocument, DraftVersion, DraftClause, FeeAgreement, Payment, Expense, ResearchItem):
        model.__table__.create(bind, checkfirst=True)

def downgrade():
    bind = op.get_bind()
    for model in (ResearchItem, Expense, Payment, FeeAgreement, DraftClause, DraftVersion, DraftDocument, DraftTemplate):
        model.__table__.drop(bind, checkfirst=True)

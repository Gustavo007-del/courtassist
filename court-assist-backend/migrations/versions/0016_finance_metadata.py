"""Extend original records with financial metadata and explicit draft expense state."""
from alembic import op
from sqlalchemy import Column,DateTime,ForeignKey,String,Text,Uuid,inspect,text
revision='0016_finance_metadata'
down_revision='0015_agreement_history'
branch_labels=None
depends_on=None
def upgrade():
    fields={
        'fee_agreements':[Column('title',String(180),nullable=False,server_default=''),Column('payment_terms',Text,nullable=False,server_default=''),Column('notes',Text,nullable=False,server_default=''),Column('updated_at',DateTime(timezone=True))],
        'payments':[Column('description',Text,nullable=False,server_default=''),Column('notes',Text,nullable=False,server_default=''),Column('receipt_number',String(60)),Column('updated_at',DateTime(timezone=True))],
        'expenses':[Column('payment_method',String(40),nullable=False,server_default='Cash'),Column('vendor',String(180),nullable=False,server_default=''),Column('reference',String(120),nullable=False,server_default=''),Column('notes',Text,nullable=False,server_default=''),Column('document_id',Uuid,ForeignKey('documents.id',name='fk_expense_document')),Column('status',String(20),nullable=False,server_default='confirmed'),Column('archived_at',DateTime(timezone=True)),Column('updated_at',DateTime(timezone=True))]}
    for name,columns in fields.items():
        existing={column['name'] for column in inspect(op.get_bind()).get_columns(name)}
        missing=[column for column in columns if column.name not in existing]
        if missing:
            with op.batch_alter_table(name) as batch:
                for column in missing:batch.add_column(column)
        op.get_bind().execute(text(f'UPDATE {name} SET updated_at=created_at WHERE updated_at IS NULL'))
def downgrade():
    # Financial history is retained; rollback requires an explicit data migration.
    pass

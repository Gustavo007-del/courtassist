"""Non-authoritative structural drafting templates."""
import uuid
from alembic import op
from sqlalchemy import text
revision='0014_draft_skeletons'
down_revision='0013_draft_exports'
branch_labels=None
depends_on=None
CATEGORIES=['Petitions','Applications','Affidavits','Vakalath','Written statements','Legal notices','Complaints','Counter affidavits','Memorandums','Agreements','General legal documents']
def upgrade():
    for category in CATEGORIES:
        identifier=str(uuid.uuid5(uuid.NAMESPACE_URL,'courtassist:skeleton:'+category)).replace('-','')
        bind=op.get_bind()
        # UUID strings use native PostgreSQL parsing, while SQLite uses compact UUID text.
        if bind.dialect.name=='postgresql':identifier=str(uuid.UUID(identifier))
        exists=bind.execute(text('SELECT id FROM draft_templates WHERE id=:id'),{'id':identifier}).first()
        if not exists:
            bind.execute(text('INSERT INTO draft_templates (id,user_id,name,category,description,content,active,version,created_at) VALUES (:id,NULL,:name,:category,:description,:content,true,1,CURRENT_TIMESTAMP)'),{'id':identifier,'name':category+' - drafting outline','category':category,'description':'Structural outline only. Not an official or verified legal form. Review and supply every substantive section.','content':'<h1>'+category+'</h1><p>{{court.name}}</p><p>{{case.number}} · {{case.title}}</p><p>{{party.names}}</p><h2>Advocate-provided content</h2><p>{{document.content}}</p><p>{{advocate.name}}<br>{{advocate.enrollment_number}}</p>'})
def downgrade():
    # Preserve templates referenced by existing drafts.
    pass

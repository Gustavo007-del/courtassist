from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from json import dumps
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.models.phase10 import DraftTemplate, DraftDocument, DraftVersion, DraftClause, FeeAgreement, Payment, Expense, ResearchItem
from app.schemas.practice import *
from app.models.case import Case
from app.models.client import Client
from app.models.document import Document
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.services.draft_placeholders import expand, workspace_values
from app.models.drafting import DraftAudit

router=APIRouter(tags=['drafting-finance-research'])

def validate_patch(schema, row, changes):
    try:
        schema.model_validate({**{key:getattr(row,key) for key in schema.model_fields},**changes})
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error

def validate_links(db,user,data):
    for key,model in (('client_id',Client),('case_id',Case),('agreement_id',FeeAgreement),('document_id',Document)):
        if data.get(key): owned(db,model,data[key],user)
    if data.get('template_id'):
        template=db.get(DraftTemplate,data['template_id'])
        if not template or template.user_id not in (None,user.id):raise HTTPException(404,'Template not found')
    if data.get('agreement_id'):
        agreement=owned(db,FeeAgreement,data['agreement_id'],user)
        if agreement.client_id!=data.get('client_id') or agreement.case_id!=data.get('case_id'):
            raise HTTPException(422,'Payment client and case must match the fee agreement')

def owned(db, model, rid, user):
    row=db.scalar(select(model).where(model.id==rid,model.user_id==user.id))
    if not row: raise HTTPException(404,'Record not found')
    return row

def dump(row):
    result={c.name:(str(getattr(row,c.name)) if isinstance(getattr(row,c.name),Decimal) else getattr(row,c.name)) for c in row.__table__.columns if c.name not in ('idempotency_key', 'request_digest')}
    if isinstance(row,(DraftDocument,DraftTemplate,DraftClause,DraftVersion)):
        from app.services.draft_generation import safe_html
        result['content']=safe_html(row.content)
    return result

def snapshot(db,row,description='Saved version'):
    db.flush();db.refresh(row,with_for_update=True)
    number=(db.scalar(select(func.max(DraftVersion.version_number)).where(DraftVersion.document_id==row.id)) or 0)+1
    version=DraftVersion(document_id=row.id,user_id=row.user_id,version_number=number,content=row.content,description=description)
    db.add(version)
    db.add(DraftAudit(user_id=row.user_id,draft_id=row.id,action='version_snapshot'))
    return version

@router.get('/draft-templates')
def templates(q:str='',category:str|None=None,archived:bool=False,limit:int=50,offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,'Invalid pagination')
    query=select(DraftTemplate).where((DraftTemplate.user_id==None)|(DraftTemplate.user_id==user.id),DraftTemplate.active.is_(not archived))
    if q:query=query.where(DraftTemplate.name.ilike(f'%{q[:200]}%'))
    if category:query=query.where(DraftTemplate.category==category)
    return [{**dump(row),'built_in':row.user_id is None} for row in db.scalars(query.order_by(DraftTemplate.name).offset(offset).limit(limit))]

@router.post('/draft-templates')
def create_template(data:TemplateInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump()
    validate_links(db,user,data)
    row=DraftTemplate(user_id=user.id,name=data.get('name','Untitled'),category=data.get('category','Other'),description=data.get('description',''),content=data.get('content',''))
    db.add(row);db.commit();db.refresh(row);return dump(row)

@router.patch('/draft-templates/{rid}')
def patch_template(rid:UUID,data:TemplatePatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump(exclude_unset=True)
    validate_links(db,user,data)
    row=owned(db,DraftTemplate,rid,user)
    validate_patch(TemplateInput,row,data)
    for k in ('name','category','description','content','active'):
        if k in data:setattr(row,k,str(data[k] or '') if k=='source_url' else data[k])
    row.version+=1;db.commit();db.refresh(row);return dump(row)

@router.delete('/draft-templates/{rid}')
def delete_template(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,DraftTemplate,rid,user);row.active=False;db.commit();return {'ok':True}

@router.get('/draft-documents')
def drafts(q:str='',category:str|None=None,status:str|None=None,archived:bool=False,limit:int=50,offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,'Invalid pagination')
    query=select(DraftDocument).where(DraftDocument.user_id==user.id,DraftDocument.archived_at.is_not(None) if archived else DraftDocument.archived_at.is_(None))
    if q:query=query.where(DraftDocument.title.ilike(f'%{q[:200]}%'))
    if category:query=query.where(DraftDocument.category==category)
    if status:query=query.where(DraftDocument.status==status)
    return [dump(x) for x in db.scalars(query.order_by(DraftDocument.updated_at.desc()).offset(offset).limit(limit)).all()]

@router.post('/draft-documents')
def create_draft(data:DraftInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump()
    validate_links(db,user,data)
    content=data.get('content','')
    if data.get('template_id') and not content:content=db.get(DraftTemplate,data['template_id']).content
    row=DraftDocument(id=db.info.get("sync_record_id"),user_id=user.id,title=data['title'],content=content,status=data['status'],case_id=data.get('case_id'),client_id=data.get('client_id'),template_id=data.get('template_id'))
    row.category=data['category'];row.language=data['language']
    db.add(row);db.flush();snapshot(db,row,'Created');db.commit();db.refresh(row);return dump(row)

@router.patch('/draft-documents/{rid}')
def update_draft(rid:UUID,data:DraftPatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump(exclude_unset=True)
    validate_links(db,user,data)
    row=db.scalar(select(DraftDocument).where(DraftDocument.id==rid,DraftDocument.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Draft not found')
    expected=data.pop('expected_updated_at',None)
    if expected and expected.replace(tzinfo=None)!=row.updated_at.replace(tzinfo=None):raise HTTPException(409,'Draft changed since it was opened')
    validate_patch(DraftInput,row,data)
    if 'content' in data and data['content']!=row.content:snapshot(db,row,'Before edit')
    for k in ('title','content','status','case_id','client_id','template_id','category','language'):
        if k in data:setattr(row,k,str(data[k] or '') if k=='source_url' else data[k])
    db.add(DraftAudit(user_id=user.id,draft_id=row.id,action='save'))
    db.commit();db.refresh(row);return dump(row)

@router.get('/draft-documents/{rid}/versions')
def versions(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    owned(db,DraftDocument,rid,user);return [dump(x) for x in db.scalars(select(DraftVersion).where(DraftVersion.document_id==rid).order_by(DraftVersion.created_at.desc())).all()]

@router.post('/draft-documents/{rid}/restore-version')
def restore(rid:UUID,data:RestoreInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump()
    row=owned(db,DraftDocument,rid,user);v=db.get(DraftVersion,data.get('version_id'))
    if not v or v.document_id!=rid: raise HTTPException(404,'Version not found')
    snapshot(db,row,'Before restore');row.content=v.content;snapshot(db,row,'Restored version');db.commit();return dump(row)

@router.get('/draft-clauses')
def clauses(q:str='',category:str|None=None,limit:int=50,offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,'Invalid pagination')
    query=select(DraftClause).where(DraftClause.user_id==user.id)
    if q:query=query.where(DraftClause.title.ilike(f'%{q[:200]}%')|DraftClause.content.ilike(f'%{q[:200]}%'))
    if category:query=query.where(DraftClause.category==category)
    return [dump(row) for row in db.scalars(query.order_by(DraftClause.title).offset(offset).limit(limit))]

@router.post('/draft-clauses')
def add_clause(data:ClauseInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump()
    validate_links(db,user,data)
    row=DraftClause(user_id=user.id,title=data['title'],category=data.get('category','General'),content=data['content'],tags=data.get('tags',[]));db.add(row);db.commit();db.refresh(row);return dump(row)

@router.patch('/draft-clauses/{rid}')
def patch_clause(rid:UUID,data:ClausePatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    data=data.model_dump(exclude_unset=True)
    validate_links(db,user,data)
    row=owned(db,DraftClause,rid,user)
    validate_patch(ClauseInput,row,data)
    for k in ('title','category','content','tags'):
        if k in data:setattr(row,k,str(data[k] or '') if k=='source_url' else data[k])
    db.commit();return dump(row)

@router.delete('/draft-clauses/{rid}')
def delete_clause(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.delete(owned(db,DraftClause,rid,user));db.commit();return {'ok':True}

@router.get('/fee-agreements')
def agreements(q:str='',client_id:UUID|None=None,case_id:UUID|None=None,from_date:date|None=None,to_date:date|None=None,limit:int=50,offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,'Invalid pagination')
    query=select(FeeAgreement).where(FeeAgreement.user_id==user.id)
    if client_id:query=query.where(FeeAgreement.client_id==client_id)
    if case_id:query=query.where(FeeAgreement.case_id==case_id)
    if from_date:query=query.where(FeeAgreement.agreement_date>=from_date)
    if to_date:query=query.where(FeeAgreement.agreement_date<=to_date)
    if q:query=query.where(FeeAgreement.description.ilike(f'%{q[:200]}%')|FeeAgreement.title.ilike(f'%{q[:200]}%'))
    return [dump(row) for row in db.scalars(query.order_by(FeeAgreement.created_at.desc()).offset(offset).limit(limit)).all()]

@router.post('/fee-agreements')
def add_agreement(data:AgreementInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    from app.services.finance_service import business_today
    provided=data.model_fields_set
    data=data.model_dump()
    if 'agreement_date' not in provided:data['agreement_date']=business_today(db,user.id)
    validate_links(db,user,data)
    row=FeeAgreement(user_id=user.id,**data)
    db.add(row);db.commit();db.refresh(row);return dump(row)

@router.get('/payments')
def payments(q:str='',client_id:UUID|None=None,case_id:UUID|None=None,from_date:date|None=None,to_date:date|None=None,limit:int=50,offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,'Invalid pagination')
    query=select(Payment).where(Payment.user_id==user.id)
    if client_id:query=query.where(Payment.client_id==client_id)
    if case_id:query=query.where(Payment.case_id==case_id)
    if from_date:query=query.where(Payment.payment_date>=from_date)
    if to_date:query=query.where(Payment.payment_date<=to_date)
    if q:query=query.where(Payment.reference.ilike(f'%{q[:200]}%')|Payment.status.ilike(f'%{q[:200]}%')|Payment.description.ilike(f'%{q[:200]}%'))
    return [dump(row) for row in db.scalars(query.order_by(Payment.payment_date.desc()).offset(offset).limit(limit)).all()]

@router.post('/payments')
def add_payment(data:PaymentInput,user:User=Depends(current_user),db:Session=Depends(get_db),idempotency_key:str=Header(min_length=8,max_length=100)):
    from app.services.finance_service import business_today
    provided=data.model_fields_set
    canonical = data.model_dump(mode='json')
    canonical['amount'] = str(data.amount.quantize(Decimal('0.01')))
    if 'payment_date' not in provided:
        canonical['payment_date'] = None
    digest = sha256(dumps(canonical, sort_keys=True).encode()).hexdigest()
    data=data.model_dump()
    if 'payment_date' not in provided:data['payment_date']=business_today(db,user.id)
    lookup = select(Payment).where(Payment.user_id==user.id, Payment.idempotency_key==idempotency_key)

    def existing_payment(row):
        matches = row and (row.request_digest == digest if row.request_digest else
                           all(getattr(row, key) == value for key, value in data.items()))
        if not matches:
            raise HTTPException(409, 'Idempotency key was used with different payment details')
        return dump(row)

    old = db.scalar(lookup)
    if old:
        return existing_payment(old)
    validate_links(db,user,data)
    row=Payment(id=db.info.get("sync_record_id"),user_id=user.id,**data,idempotency_key=idempotency_key,request_digest=digest)
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        return existing_payment(db.scalar(lookup))
    db.refresh(row);return dump(row)

@router.get('/expenses')
def expenses(q:str='',archived:bool=False,client_id:UUID|None=None,case_id:UUID|None=None,from_date:date|None=None,to_date:date|None=None,limit:int=50,offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,'Invalid pagination')
    query=select(Expense).where(Expense.user_id==user.id,Expense.archived_at.is_not(None) if archived else Expense.archived_at.is_(None))
    if client_id:query=query.where(Expense.client_id==client_id)
    if case_id:query=query.where(Expense.case_id==case_id)
    if from_date:query=query.where(Expense.expense_date>=from_date)
    if to_date:query=query.where(Expense.expense_date<=to_date)
    if q:query=query.where(Expense.description.ilike(f'%{q[:200]}%')|Expense.category.ilike(f'%{q[:200]}%')|Expense.vendor.ilike(f'%{q[:200]}%')|Expense.reference.ilike(f'%{q[:200]}%'))
    return [dump(row) for row in db.scalars(query.order_by(Expense.expense_date.desc()).offset(offset).limit(limit)).all()]

@router.post('/expenses')
def add_expense(data:ExpenseInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    from app.services.finance_service import business_today
    provided=data.model_fields_set
    data=data.model_dump()
    if 'expense_date' not in provided:data['expense_date']=business_today(db,user.id)
    validate_links(db,user,data)
    row=Expense(user_id=user.id,**data);db.add(row);db.commit();db.refresh(row);return dump(row)

@router.get('/finance/reports/monthly')
def monthly_report(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Payment).where(Payment.user_id==user.id,Payment.status=='received')).all()
    totals={}
    for row in rows:
        key=row.payment_date.strftime('%Y-%m')
        totals[key]=totals.get(key,Decimal('0'))+row.amount
    return [{'month':month,'income':totals[month]} for month in sorted(totals)]

@router.get('/finance/summary')
def finance_summary(from_date:date|None=None,to_date:date|None=None,client_id:UUID|None=None,case_id:UUID|None=None,user:User=Depends(current_user),db:Session=Depends(get_db)):
    from app.services.finance_service import summary
    if from_date and to_date and from_date>to_date:raise HTTPException(422,'Invalid date range')
    return summary(db,user.id,from_date,to_date,client_id,case_id)
@router.get('/draft-templates/{rid}')
def template_detail(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(DraftTemplate,rid)
    if not row or row.user_id not in (None,user.id):raise HTTPException(404,'Template not found')
    return {**dump(row),'built_in':row.user_id is None}

@router.post('/draft-templates/{rid}/duplicate',status_code=201)
def duplicate_template(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    source=template_detail(rid,user,db)
    row=DraftTemplate(user_id=user.id,name=source['name'][:170]+' (copy)',category=source['category'],description=source['description'],content=source['content'])
    db.add(row);db.commit();db.refresh(row);return dump(row)

@router.get('/draft-documents/{rid}')
def draft_detail(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,DraftDocument,rid,user)
    return {**dump(row),'missing_placeholders':expand(row.content,{})['missing_placeholders']}

@router.get('/draft-documents/{rid}/autofill')
def draft_autofill(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,DraftDocument,rid,user)
    case=owned(db,Case,row.case_id,user) if row.case_id else None
    client=owned(db,Client,row.client_id,user) if row.client_id else None
    return expand(row.content,workspace_values(user,client,case))

@router.delete('/draft-documents/{rid}')
def delete_draft(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return archive_draft(rid,user,db)

@router.post('/draft-documents/{rid}/archive')
def archive_draft(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,DraftDocument,rid,user);row.archived_at=datetime.now(timezone.utc);db.add(DraftAudit(user_id=user.id,draft_id=row.id,action='archive'));db.commit();return dump(row)

@router.post('/draft-documents/{rid}/restore')
def restore_draft(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,DraftDocument,rid,user);row.archived_at=None;db.add(DraftAudit(user_id=user.id,draft_id=row.id,action='restore'));db.commit();return dump(row)

@router.post('/draft-documents/{rid}/duplicate',status_code=201)
def duplicate_draft(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    source=owned(db,DraftDocument,rid,user)
    row=DraftDocument(user_id=user.id,title=source.title[:170]+' (copy)',content=source.content,category=source.category,language=source.language,status='draft',case_id=source.case_id,client_id=source.client_id,template_id=source.template_id)
    db.add(row);db.flush();snapshot(db,row,'Duplicated draft');db.commit();return dump(row)

@router.post('/draft-documents/{rid}/versions',status_code=201)
def manual_version(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,DraftDocument,rid,user);version=snapshot(db,row,'Manual snapshot');db.commit();return dump(version)

@router.post('/draft-documents/{rid}/versions/{version_id}/restore')
def restore_version(rid:UUID,version_id:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return restore(rid,RestoreInput(version_id=version_id),user,db)

@router.get('/draft-clauses/{rid}')
def clause_detail(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return dump(owned(db,DraftClause,rid,user))

@router.get('/fee-agreements/{rid}')
def agreement_detail(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,FeeAgreement,rid,user)
    received=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.user_id==user.id,Payment.agreement_id==rid,Payment.status=='received'))
    return {**dump(row),'received':str(received),'outstanding':str(max(Decimal(0),row.amount-received))}

@router.get('/payments/{rid}')
def payment_detail(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return dump(owned(db,Payment,rid,user))

@router.get('/expenses/{rid}')
def expense_detail(rid:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return dump(owned(db,Expense,rid,user))


from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.models.diary import CaseDiaryEntry
from app.models.case import Case
from app.models.hearing import Hearing
from app.models.user import User
from app.schemas.diary import DiaryCreate, DiaryOut, DiaryUpdate
from app.services.case_service import log, owned_case
from app.services.hearing_service import owned_hearing

def owned_entry(db: Session, user: User, entry_id: UUID, lock=False) -> CaseDiaryEntry:
    query = select(CaseDiaryEntry).where(CaseDiaryEntry.id == entry_id, CaseDiaryEntry.user_id == user.id, CaseDiaryEntry.case.has(Case.user_id == user.id))
    if lock: query = query.with_for_update()
    item = db.scalar(query)
    if item is None: raise HTTPException(404, 'Diary entry not found')
    return item

def check_hearing(db, user, hearing_id, case_id):
    if hearing_id is None: return
    hearing = owned_hearing(db, user, hearing_id)
    if hearing.case_id != case_id: raise HTTPException(422, 'Hearing does not belong to this case')

def serialize(item: CaseDiaryEntry) -> DiaryOut:
    return DiaryOut.model_validate({**item.__dict__, 'case_title': item.case.case_title,
        'case_number': item.case.case_number, 'hearing_date': item.hearing.hearing_date if item.hearing else None})

def list_entries(db, user, limit, offset, case_id=None, hearing_id=None, q=None, category=None, from_date=None, to_date=None, important=None, pinned=None, order='newest'):
    filters = [CaseDiaryEntry.user_id == user.id, CaseDiaryEntry.case.has(Case.user_id == user.id)]
    if case_id: owned_case(db, user, case_id, include_archived=True); filters.append(CaseDiaryEntry.case_id == case_id)
    if hearing_id:
        hearing = owned_hearing(db, user, hearing_id)
        if case_id and hearing.case_id != case_id: raise HTTPException(422, 'Hearing does not belong to this case')
        filters.append(CaseDiaryEntry.hearing_id == hearing_id)
    if category: filters.append(CaseDiaryEntry.entry_type == category)
    if from_date: filters.append(CaseDiaryEntry.entry_date >= from_date)
    if to_date: filters.append(CaseDiaryEntry.entry_date <= to_date)
    if important is not None: filters.append(CaseDiaryEntry.is_important == important)
    if pinned is not None: filters.append(CaseDiaryEntry.is_pinned == pinned)
    if q:
        term = f'%{q.strip()}%'
        filters.append(or_(CaseDiaryEntry.title.ilike(term), CaseDiaryEntry.content.ilike(term)))
    total = db.scalar(select(func.count()).select_from(CaseDiaryEntry).where(*filters)) or 0
    sort = (CaseDiaryEntry.entry_date.asc(), CaseDiaryEntry.created_at.asc(), CaseDiaryEntry.id.asc()) if order == 'oldest' else (CaseDiaryEntry.entry_date.desc(), CaseDiaryEntry.created_at.desc(), CaseDiaryEntry.id.desc())
    items = db.scalars(select(CaseDiaryEntry).options(selectinload(CaseDiaryEntry.case), selectinload(CaseDiaryEntry.hearing)).where(*filters).order_by(*sort).offset(offset).limit(limit)).all()
    return total, [serialize(item) for item in items]

def create(db, user, data: DiaryCreate):
    case = owned_case(db, user, data.case_id, include_archived=True)
    check_hearing(db, user, data.hearing_id, case.id)
    item = CaseDiaryEntry(user_id=user.id, **data.model_dump())
    db.add(item); db.flush()
    log(db, user, case, 'diary_created', 'Private diary entry created', details={'diary_entry_id': str(item.id), 'important': item.is_important})
    db.commit()
    return serialize(owned_entry(db, user, item.id))

def update(db, user, entry_id, data: DiaryUpdate):
    item = owned_entry(db, user, entry_id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, 'Provide at least one field')
    for required in ('entry_date', 'entry_type', 'title', 'content', 'is_important', 'is_pinned'):
        if required in changes and changes[required] is None: raise HTTPException(422, f'{required} cannot be null')
    if 'hearing_id' in changes: check_hearing(db, user, changes['hearing_id'], item.case_id)
    fields = []
    for key, value in changes.items():
        if getattr(item, key) != value: setattr(item, key, value); fields.append(key)
    if fields:
        log(db, user, item.case, 'diary_updated', 'Private diary entry updated', details={'diary_entry_id': str(item.id), 'fields': fields, 'important': item.is_important})
        db.commit()
    return serialize(owned_entry(db, user, item.id))

def delete(db, user, entry_id):
    item = owned_entry(db, user, entry_id, lock=True)
    log(db, user, item.case, 'diary_deleted', 'Private diary entry deleted', details={'diary_entry_id': str(item.id)})
    db.delete(item); db.commit()

def flag(db, user, entry_id, field, value):
    item = owned_entry(db, user, entry_id, lock=True)
    if getattr(item, field) != value:
        setattr(item, field, value)
        log(db, user, item.case, 'diary_updated', 'Private diary entry updated', details={'diary_entry_id': str(item.id), 'fields': [field], 'important': item.is_important})
        db.commit()
    return serialize(owned_entry(db, user, item.id))

from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.diary import DiaryCreate, DiaryOut, DiaryPage, DiaryUpdate
from app.services import diary_service as service
from app.services.case_service import owned_case
from app.services.hearing_service import owned_hearing

router = APIRouter(tags=['diary'])

def page(db, user, limit, offset, **filters):
    total, items = service.list_entries(db, user, limit, offset, **filters)
    return DiaryPage(items=items, total=total, limit=limit, offset=offset)

@router.get('/diary', response_model=DiaryPage)
def entries(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), case_id: UUID | None = None, hearing_id: UUID | None = None, q: str | None = Query(None, max_length=200), category: str | None = None, from_date: date | None = None, to_date: date | None = None, important: bool | None = None, pinned: bool | None = None, order: Literal['newest', 'oldest'] = 'newest'):
    return page(db, user, limit, offset, case_id=case_id, hearing_id=hearing_id, q=q, category=category, from_date=from_date, to_date=to_date, important=important, pinned=pinned, order=order)

@router.post('/diary', response_model=DiaryOut, status_code=201)
def create(data: DiaryCreate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.create(db, user, data)

@router.get('/diary/{entry_id}', response_model=DiaryOut)
def detail(entry_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.serialize(service.owned_entry(db, user, entry_id))

@router.patch('/diary/{entry_id}', response_model=DiaryOut)
def update(entry_id: UUID, data: DiaryUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.update(db, user, entry_id, data)

@router.delete('/diary/{entry_id}', status_code=204)
def delete(entry_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): service.delete(db, user, entry_id)

@router.post('/diary/{entry_id}/pin', response_model=DiaryOut)
def pin(entry_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.flag(db, user, entry_id, 'is_pinned', True)

@router.delete('/diary/{entry_id}/pin', response_model=DiaryOut)
def unpin(entry_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.flag(db, user, entry_id, 'is_pinned', False)

@router.post('/diary/{entry_id}/important', response_model=DiaryOut)
def important(entry_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.flag(db, user, entry_id, 'is_important', True)

@router.delete('/diary/{entry_id}/important', response_model=DiaryOut)
def unimportant(entry_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.flag(db, user, entry_id, 'is_important', False)

@router.get('/cases/{case_id}/diary', response_model=DiaryPage)
def case_entries(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return page(db, user, limit, offset, case_id=case_id)

@router.post('/cases/{case_id}/diary', response_model=DiaryOut, status_code=201)
def case_create(case_id: UUID, data: DiaryCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(db, user, case_id, include_archived=True)
    if data.case_id != case_id:
        from fastapi import HTTPException
        raise HTTPException(422, 'Case mismatch')
    return service.create(db, user, data)

@router.get('/hearings/{hearing_id}/diary', response_model=DiaryPage)
def hearing_entries(hearing_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    owned_hearing(db, user, hearing_id)
    return page(db, user, limit, offset, hearing_id=hearing_id)

@router.post('/hearings/{hearing_id}/diary', response_model=DiaryOut, status_code=201)
def hearing_create(hearing_id: UUID, data: DiaryCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    hearing = owned_hearing(db, user, hearing_id)
    if data.hearing_id != hearing_id or data.case_id != hearing.case_id:
        from fastapi import HTTPException
        raise HTTPException(422, 'Hearing or case mismatch')
    return service.create(db, user, data)

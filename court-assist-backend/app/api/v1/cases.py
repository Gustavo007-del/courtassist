from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.case import CaseAdvocate, CaseParty, CaseStatusHistory
from app.models.user import User
from app.schemas.case import ActivityPage, AdvocateFields, AdvocateOut, CaseCreate, CaseOut, CasePage, CaseUpdate, PartyFields, PartyOut, StatusChange, StatusOut
from app.services import case_service as service

router = APIRouter(prefix='/cases', tags=['cases'])

@router.get('', response_model=CasePage)
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), q: str | None = Query(None, max_length=160), category: str | None = Query(None, max_length=80), status: str | None = Query(None, max_length=32), district: str | None = Query(None, max_length=120), priority: Literal['Normal', 'High', 'Urgent'] | None = None, archived: bool = False, sort: Literal['updated', 'filing', 'alphabetical'] = 'updated', client_id: UUID | None = None):
    total, items = service.list_cases(db, user, limit, offset, q, category, status, district, priority, archived, sort, client_id)
    return CasePage(items=items, total=total, limit=limit, offset=offset)

@router.post('', response_model=CaseOut, status_code=201)
def create(data: CaseCreate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.create_case(db, user, data)

@router.get('/{case_id}', response_model=CaseOut)
def detail(case_id: UUID, include_archived: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.serialize(service.owned_case(db, user, case_id, include_archived))

@router.patch('/{case_id}', response_model=CaseOut)
def update(case_id: UUID, data: CaseUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.update_case(db, user, case_id, data)

@router.post('/{case_id}/archive', response_model=CaseOut)
def archive(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.set_archive(db, user, case_id, True)

@router.post('/{case_id}/restore', response_model=CaseOut)
def restore(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.set_archive(db, user, case_id, False)

@router.get('/{case_id}/parties', response_model=list[PartyOut])
def parties(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.owned_case(db, user, case_id, include_archived=True)
    return db.scalars(select(CaseParty).where(CaseParty.case_id == case_id, CaseParty.user_id == user.id).order_by(CaseParty.created_at, CaseParty.id)).all()

@router.post('/{case_id}/parties', response_model=PartyOut, status_code=201)
def add_party(case_id: UUID, data: PartyFields, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.mutate_party(db, user, case_id, data)

@router.patch('/{case_id}/parties/{party_id}', response_model=PartyOut)
def update_party(case_id: UUID, party_id: UUID, data: PartyFields, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.mutate_party(db, user, case_id, data, party_id)

@router.delete('/{case_id}/parties/{party_id}', status_code=204)
def delete_party(case_id: UUID, party_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): service.delete_party(db, user, case_id, party_id)

@router.get('/{case_id}/advocates', response_model=list[AdvocateOut])
def advocates(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.owned_case(db, user, case_id, include_archived=True)
    return db.scalars(select(CaseAdvocate).where(CaseAdvocate.case_id == case_id, CaseAdvocate.user_id == user.id).order_by(CaseAdvocate.is_primary.desc(), CaseAdvocate.created_at)).all()

@router.post('/{case_id}/advocates', response_model=AdvocateOut, status_code=201)
def add_advocate(case_id: UUID, data: AdvocateFields, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.mutate_advocate(db, user, case_id, data)

@router.patch('/{case_id}/advocates/{advocate_id}', response_model=AdvocateOut)
def update_advocate(case_id: UUID, advocate_id: UUID, data: AdvocateFields, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.mutate_advocate(db, user, case_id, data, advocate_id)

@router.delete('/{case_id}/advocates/{advocate_id}', status_code=204)
def delete_advocate(case_id: UUID, advocate_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): service.delete_advocate(db, user, case_id, advocate_id)

@router.get('/{case_id}/status-history', response_model=list[StatusOut])
def history(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.owned_case(db, user, case_id, include_archived=True)
    return db.scalars(select(CaseStatusHistory).where(CaseStatusHistory.case_id == case_id, CaseStatusHistory.user_id == user.id).order_by(CaseStatusHistory.created_at.desc(), CaseStatusHistory.id.desc())).all()

@router.post('/{case_id}/status', response_model=StatusOut)
def change_status(case_id: UUID, data: StatusChange, user: User = Depends(current_user), db: Session = Depends(get_db)): return service.change_status(db, user, case_id, data)

@router.get('/{case_id}/activities', response_model=ActivityPage)
def activities(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    total, items = service.events(db, user, case_id, limit, offset)
    return ActivityPage(items=items, total=total, limit=limit, offset=offset)

@router.get('/{case_id}/timeline', response_model=ActivityPage)
def timeline(case_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0), order: Literal['newest', 'oldest'] = 'newest', category: Literal['case', 'status', 'hearing', 'diary'] | None = None, from_date: date | None = None, to_date: date | None = None):
    total, items = service.events(db, user, case_id, limit, offset, order == 'oldest', category, from_date, to_date)
    return ActivityPage(items=items, total=total, limit=limit, offset=offset)

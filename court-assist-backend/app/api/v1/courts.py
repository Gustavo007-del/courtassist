from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.court import CourtCreate, CourtOut, CourtPage, CourtUpdate
from app.services import court_service

router = APIRouter(prefix='/courts', tags=['courts'])


@router.get('', response_model=CourtPage)
def courts(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), q: str | None = Query(None, max_length=240), court_type: str | None = Query(None, max_length=64), district: str | None = Query(None, max_length=120), state: str | None = Query(None, max_length=120)):
    total, items = court_service.list_courts(db, user, limit, offset, q, court_type, district, state)
    return CourtPage(items=items, total=total, limit=limit, offset=offset)


@router.get('/favorites', response_model=CourtPage)
def favorites(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    total, items = court_service.list_courts(db, user, limit, offset, favorites=True)
    return CourtPage(items=items, total=total, limit=limit, offset=offset)


@router.post('', response_model=CourtOut, status_code=201)
def create_court(data: CourtCreate, user: User = Depends(current_user), db: Session = Depends(get_db)): return court_service.create_court(db, user, data)


@router.get('/{court_id}', response_model=CourtOut)
def court(court_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return court_service.get_court(db, user, court_id)


@router.patch('/{court_id}', response_model=CourtOut)
def update_court(court_id: UUID, data: CourtUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return court_service.update_court(db, user, court_id, data)


@router.delete('/{court_id}', status_code=204)
def delete_court(court_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): court_service.delete_court(db, user, court_id)


@router.post('/{court_id}/favorite', response_model=MessageOut)
def favorite(court_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): court_service.favorite(db, user, court_id); return MessageOut(detail='Court added to favorites')


@router.delete('/{court_id}/favorite', status_code=204)
def unfavorite(court_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): court_service.unfavorite(db, user, court_id)

from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
from app.models.case import Case, CaseParty
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.client import ClientCreate, ClientOut, ClientPage, ClientUpdate, InteractionIn, InteractionOut, InteractionUpdate, NoteIn, NoteOut, NoteUpdate
from app.services import client_service

router = APIRouter(prefix='/clients', tags=['clients'])

def with_count(db: Session, user: User, item):
    count = db.scalar(select(func.count()).select_from(Case).where(Case.user_id == user.id, Case.is_archived.is_(False), or_(Case.client_id == item.id, Case.id.in_(select(CaseParty.case_id).where(CaseParty.user_id == user.id, CaseParty.client_id == item.id))))) or 0
    return {**ClientOut.model_validate(item).model_dump(), 'associated_case_count': count}


@router.get('', response_model=ClientPage)
def clients(user: User = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), q: str | None = Query(None, max_length=160), client_type: Literal['individual', 'organization'] | None = None, archived: bool = False, sort: Literal['recent', 'alphabetical'] = 'recent'):
    total, items = client_service.list_clients(db, user, limit, offset, q, client_type, archived, sort)
    return ClientPage(items=[with_count(db, user, item) for item in items], total=total, limit=limit, offset=offset)


@router.post('', response_model=ClientOut, status_code=201)
def create_client(data: ClientCreate, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.create_client(db, user, data)


@router.get('/{client_id}', response_model=ClientOut)
def client(client_id: UUID, include_archived: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)): return with_count(db, user, client_service.owned_client(db, user, client_id, include_archived))


@router.patch('/{client_id}', response_model=ClientOut)
def update_client(client_id: UUID, data: ClientUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.update_client(db, user, client_id, data)


@router.delete('/{client_id}', status_code=204)
def delete_client(client_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): client_service.soft_delete(db, user, client_id)


@router.post('/{client_id}/archive', response_model=ClientOut)
def archive(client_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.set_archive(db, user, client_id, True)


@router.post('/{client_id}/restore', response_model=ClientOut)
def restore(client_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.set_archive(db, user, client_id, False)


@router.get('/{client_id}/notes', response_model=list[NoteOut])
def notes(client_id: UUID, q: str | None = Query(None, max_length=160), user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.list_notes(db, user, client_id, q)


@router.post('/{client_id}/notes', response_model=NoteOut, status_code=201)
def create_note(client_id: UUID, data: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.create_note(db, user, client_id, data)


@router.patch('/{client_id}/notes/{note_id}', response_model=NoteOut)
def update_note(client_id: UUID, note_id: UUID, data: NoteUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.update_note(db, user, client_id, note_id, data)


@router.delete('/{client_id}/notes/{note_id}', status_code=204)
def delete_note(client_id: UUID, note_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): client_service.delete_note(db, user, client_id, note_id)


@router.get('/{client_id}/interactions', response_model=list[InteractionOut])
def interactions(client_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.list_interactions(db, user, client_id)


@router.post('/{client_id}/interactions', response_model=InteractionOut, status_code=201)
def create_interaction(client_id: UUID, data: InteractionIn, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.create_interaction(db, user, client_id, data)


@router.patch('/{client_id}/interactions/{interaction_id}', response_model=InteractionOut)
def update_interaction(client_id: UUID, interaction_id: UUID, data: InteractionUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)): return client_service.update_interaction(db, user, client_id, interaction_id, data)


@router.delete('/{client_id}/interactions/{interaction_id}', status_code=204)
def delete_interaction(client_id: UUID, interaction_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)): client_service.delete_interaction(db, user, client_id, interaction_id)

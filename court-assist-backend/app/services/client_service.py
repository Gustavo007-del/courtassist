from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.client import Client, ClientInteraction, ClientNote
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate, InteractionIn, InteractionUpdate, NoteIn, NoteUpdate
from app.services.activity_service import record_activity


def owned_client(db: Session, user: User, client_id: UUID, include_archived=False) -> Client:
    filters = [Client.id == client_id, Client.user_id == user.id, Client.deleted_at.is_(None)]
    if not include_archived: filters.append(Client.is_archived.is_(False))
    client = db.scalar(select(Client).where(*filters))
    if not client: raise HTTPException(404, 'Client not found')
    return client


def list_clients(db, user, limit, offset, q=None, client_type=None, archived=False, sort='recent'):
    filters = [Client.user_id == user.id, Client.deleted_at.is_(None), Client.is_archived == archived]
    if client_type: filters.append(Client.client_type == client_type)
    if q:
        term = f'%{q.strip()}%'
        filters.append(or_(Client.full_name.ilike(term), Client.organization_name.ilike(term), Client.phone_number.ilike(term), Client.email.ilike(term)))
    order = Client.full_name.asc() if sort == 'alphabetical' else Client.created_at.desc()
    total = db.scalar(select(func.count()).select_from(Client).where(*filters)) or 0
    items = db.scalars(select(Client).where(*filters).order_by(order, Client.id).offset(offset).limit(limit)).all()
    return total, items


def create_client(db: Session, user: User, data: ClientCreate) -> Client:
    client = Client(user_id=user.id, **data.model_dump())
    db.add(client); db.flush()
    record_activity(db, user.id, 'client_created', 'Client created', entity_type='client', entity_id=client.id)
    db.commit(); db.refresh(client); return client


def update_client(db, user, client_id, data: ClientUpdate):
    client = owned_client(db, user, client_id, include_archived=True)
    changes = data.model_dump(exclude_unset=True)
    future_type = changes.get('client_type', client.client_type)
    future_org = changes.get('organization_name', client.organization_name)
    if future_type == 'organization' and not future_org: raise HTTPException(422, 'Organization name is required')
    if not changes: raise HTTPException(422, 'Provide at least one field')
    changed = []
    for key, value in changes.items():
        if getattr(client, key) != value: setattr(client, key, value); changed.append(key)
    if changed:
        record_activity(db, user.id, 'client_updated', 'Client updated', entity_type='client', entity_id=client.id, details={'fields': changed})
        db.commit(); db.refresh(client)
    return client


def set_archive(db, user, client_id, archived):
    client = owned_client(db, user, client_id, include_archived=True)
    client.is_archived = archived
    record_activity(db, user.id, 'client_archived' if archived else 'client_restored', 'Client archived' if archived else 'Client restored', entity_type='client', entity_id=client.id)
    db.commit(); db.refresh(client); return client


def soft_delete(db, user, client_id):
    client = owned_client(db, user, client_id, include_archived=True)
    client.deleted_at = datetime.now(timezone.utc); client.is_archived = True
    record_activity(db, user.id, 'client_deleted', 'Client deleted', entity_type='client', entity_id=client.id)
    db.commit()


def list_notes(db, user, client_id, q=None):
    owned_client(db, user, client_id, include_archived=True)
    filters = [ClientNote.client_id == client_id, ClientNote.user_id == user.id]
    if q: filters.append(or_(ClientNote.title.ilike(f'%{q}%'), ClientNote.content.ilike(f'%{q}%')))
    return db.scalars(select(ClientNote).where(*filters).order_by(ClientNote.created_at.desc())).all()


def create_note(db, user, client_id, data: NoteIn):
    owned_client(db, user, client_id, include_archived=True)
    note = ClientNote(client_id=client_id, user_id=user.id, **data.model_dump()); db.add(note); db.flush()
    record_activity(db, user.id, 'client_note_added', 'Client note added', entity_type='client', entity_id=client_id)
    db.commit(); db.refresh(note); return note


def _note(db, user, client_id, note_id):
    owned_client(db, user, client_id, include_archived=True)
    note = db.scalar(select(ClientNote).where(ClientNote.id == note_id, ClientNote.client_id == client_id, ClientNote.user_id == user.id))
    if not note: raise HTTPException(404, 'Note not found')
    return note


def update_note(db, user, client_id, note_id, data: NoteUpdate):
    note = _note(db, user, client_id, note_id); changes = data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, 'Provide at least one field')
    for k, v in changes.items(): setattr(note, k, v)
    db.commit(); db.refresh(note); return note


def delete_note(db, user, client_id, note_id):
    db.delete(_note(db, user, client_id, note_id)); db.commit()


def list_interactions(db, user, client_id):
    owned_client(db, user, client_id, include_archived=True)
    return db.scalars(select(ClientInteraction).where(ClientInteraction.client_id == client_id, ClientInteraction.user_id == user.id).order_by(ClientInteraction.interaction_date.desc())).all()


def create_interaction(db, user, client_id, data: InteractionIn):
    owned_client(db, user, client_id, include_archived=True)
    item = ClientInteraction(client_id=client_id, user_id=user.id, **data.model_dump()); db.add(item); db.flush()
    record_activity(db, user.id, 'client_interaction_added', 'Client interaction added', entity_type='client', entity_id=client_id)
    db.commit(); db.refresh(item); return item


def _interaction(db, user, client_id, interaction_id):
    owned_client(db, user, client_id, include_archived=True)
    item = db.scalar(select(ClientInteraction).where(ClientInteraction.id == interaction_id, ClientInteraction.client_id == client_id, ClientInteraction.user_id == user.id))
    if not item: raise HTTPException(404, 'Interaction not found')
    return item


def update_interaction(db, user, client_id, interaction_id, data: InteractionUpdate):
    item = _interaction(db, user, client_id, interaction_id); changes = data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, 'Provide at least one field')
    for k, v in changes.items(): setattr(item, k, v)
    required = changes.get('follow_up_required', item.follow_up_required)
    follow_date = changes.get('follow_up_date', item.follow_up_date)
    if required and not follow_date: raise HTTPException(422, 'Follow-up date is required')
    if not required: item.follow_up_date = None
    db.commit(); db.refresh(item); return item


def delete_interaction(db, user, client_id, interaction_id):
    db.delete(_interaction(db, user, client_id, interaction_id)); db.commit()

from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.models.case import Case, CaseActivity, CaseAdvocate, CaseParty, CaseStatusHistory
from app.models.client import Client
from app.models.court import Court
from app.models.user import User
from app.schemas.case import AdvocateFields, CaseCreate, CaseUpdate, PartyFields, StatusChange
from app.services.activity_service import record_activity

DISPOSED = {'Disposed', 'Dismissed', 'Withdrawn', 'Settled', 'Transferred'}

def owned_case(db: Session, user: User, case_id: UUID, include_archived=False, lock=False) -> Case:
    statement = select(Case).where(Case.id == case_id, Case.user_id == user.id)
    if not include_archived: statement = statement.where(Case.is_archived.is_(False))
    if lock: statement = statement.with_for_update()
    item = db.scalar(statement)
    if item is None: raise HTTPException(404, 'Case not found')
    return item

def check_client(db, user, client_id):
    if client_id is None: return None
    client = db.scalar(select(Client).where(Client.id == client_id, Client.user_id == user.id, Client.deleted_at.is_(None)))
    if client is None: raise HTTPException(404, 'Client not found')
    return client

def check_court(db, user, court_id):
    if court_id is None: return None
    court = db.scalar(select(Court).where(Court.id == court_id, Court.is_active.is_(True), or_(Court.user_id.is_(None), Court.user_id == user.id)))
    if court is None: raise HTTPException(404, 'Court not found')
    return court

def serialize(item: Case):
    from app.schemas.case import CaseOut
    return CaseOut.model_validate({**item.__dict__, 'court_name': item.court.name if item.court else None,
        'court_district': item.court.district if item.court else None,
        'primary_client_name': item.primary_client.full_name if item.primary_client and item.primary_client.deleted_at is None else None})

def log(db, user, item, kind, title, description=None, details=None):
    db.add(CaseActivity(case_id=item.id, user_id=user.id, activity_type=kind, title=title, description=description, details=details or {}))
    record_activity(db, user.id, kind, title, description=description, entity_type='case', entity_id=item.id, details=details or {})

def duplicate_check(db, user, court_id, case_number, cnr_number, excluding=None):
    if court_id is None: return
    base = [Case.user_id == user.id, Case.court_id == court_id]
    if excluding: base.append(Case.id != excluding)
    if db.scalar(select(Case.id).where(*base, func.lower(Case.case_number) == case_number.lower()).limit(1)):
        raise HTTPException(409, 'Case number already exists for this court')
    if cnr_number and db.scalar(select(Case.id).where(*base, func.lower(Case.cnr_number) == cnr_number.lower()).limit(1)):
        raise HTTPException(409, 'CNR number already exists for this court')

def add_party_record(db, user, item, data: PartyFields):
    values = data.model_dump()
    if data.client_id:
        client = check_client(db, user, data.client_id)
        values.update(party_name=client.full_name, party_type=client.client_type, address=client.address,
            phone_number=client.phone_number, email=client.email)
    party = CaseParty(case_id=item.id, user_id=user.id, **values)
    db.add(party)
    log(db, user, item, 'case_party_added', 'Party added', details={'role': party.party_role})
    return party

def add_advocate_record(db, user, item, data: AdvocateFields):
    if data.is_primary and db.scalar(select(CaseAdvocate.id).where(CaseAdvocate.case_id == item.id, CaseAdvocate.is_primary.is_(True))):
        raise HTTPException(409, 'A primary advocate already exists')
    advocate = CaseAdvocate(case_id=item.id, user_id=user.id, **data.model_dump())
    db.add(advocate)
    log(db, user, item, 'case_advocate_added', 'Advocate representation added', details={'role': data.representation_role})
    return advocate

def create_case(db, user, data: CaseCreate):
    if data.initial_status == 'Archived': raise HTTPException(422, 'Use the archive endpoint')
    check_client(db, user, data.client_id); check_court(db, user, data.court_id)
    for party in data.parties: check_client(db, user, party.client_id)
    duplicate_check(db, user, data.court_id, data.case_number, data.cnr_number)
    values = data.model_dump(exclude={'initial_status', 'parties', 'advocates'})
    item = Case(id=db.info.get("sync_record_id"), user_id=user.id, current_status=data.initial_status, disposed_at=datetime.now(timezone.utc) if data.initial_status in DISPOSED else None, **values)
    db.add(item); db.flush()
    log(db, user, item, 'case_created', 'Case created')
    db.add(CaseStatusHistory(case_id=item.id, user_id=user.id, previous_status=data.initial_status, new_status=data.initial_status, effective_date=data.filing_date))
    for party in data.parties: add_party_record(db, user, item, party)
    db.add(CaseAdvocate(case_id=item.id, user_id=user.id, advocate_name=user.full_name, bar_registration_number=user.enrollment_number, representation_role='Counsel for client', is_primary=True))
    for advocate in data.advocates:
        if advocate.is_primary: raise HTTPException(422, 'The logged-in advocate is already primary')
        add_advocate_record(db, user, item, advocate)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Duplicate case reference')
    return serialize(owned_case(db, user, item.id, include_archived=True))

def update_case(db, user, case_id, data: CaseUpdate):
    item = owned_case(db, user, case_id, include_archived=True, lock=True)
    if item.is_archived: raise HTTPException(409, 'Restore the case before editing')
    changes = data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, 'Provide at least one field')
    if 'client_id' in changes: check_client(db, user, changes['client_id'])
    if 'court_id' in changes: check_court(db, user, changes['court_id'])
    if any(key in changes for key in ('court_id', 'case_number', 'cnr_number')):
        duplicate_check(db, user, changes.get('court_id', item.court_id), changes.get('case_number', item.case_number), changes.get('cnr_number', item.cnr_number), excluding=item.id)
    if changes.get('registration_date', item.registration_date) and changes.get('filing_date', item.filing_date) and changes.get('registration_date', item.registration_date) < changes.get('filing_date', item.filing_date):
        raise HTTPException(422, 'Registration date cannot precede filing date')
    fields = []
    for key, value in changes.items():
        if getattr(item, key) != value: setattr(item, key, value); fields.append(key)
    if fields:
        log(db, user, item, 'case_updated', 'Case updated', details={'fields': fields})
        try: db.commit()
        except IntegrityError:
            db.rollback(); raise HTTPException(409, 'Duplicate case reference')
    return serialize(owned_case(db, user, case_id, include_archived=True))

def change_status(db, user, case_id, data: StatusChange):
    item = owned_case(db, user, case_id, include_archived=True, lock=True)
    if item.is_archived: raise HTTPException(409, 'Restore the case before changing status')
    if data.new_status == 'Archived': raise HTTPException(422, 'Use the archive endpoint')
    if item.current_status == data.new_status: raise HTTPException(409, 'Case already has this status')
    previous = item.current_status
    history = CaseStatusHistory(case_id=item.id, user_id=user.id, previous_status=previous, new_status=data.new_status, reason=data.reason, effective_date=data.effective_date)
    item.current_status = data.new_status
    item.disposed_at = datetime.now(timezone.utc) if data.new_status in DISPOSED else None
    db.add(history)
    log(db, user, item, 'case_status_changed', 'Case status changed', details={'previous': previous, 'new': data.new_status})
    db.commit(); db.refresh(history)
    return history

def set_archive(db, user, case_id, archived):
    item = owned_case(db, user, case_id, include_archived=True, lock=True)
    if item.is_archived == archived: return serialize(item)
    item.is_archived = archived
    log(db, user, item, 'case_archived' if archived else 'case_restored', 'Case archived' if archived else 'Case restored')
    db.commit()
    return serialize(owned_case(db, user, case_id, include_archived=True))

def list_cases(db, user, limit, offset, q=None, category=None, status=None, district=None, priority=None, archived=False, sort='updated', client_id=None):
    filters = [Case.user_id == user.id, Case.is_archived == archived]
    if category: filters.append(Case.case_category == category)
    if status: filters.append(Case.current_status == status)
    if priority: filters.append(Case.priority == priority)
    if client_id: filters.append(or_(Case.client_id == client_id, Case.id.in_(select(CaseParty.case_id).where(CaseParty.client_id == client_id, CaseParty.user_id == user.id))))
    if district: filters.append(Case.court.has(func.lower(Court.district) == district.lower()))
    if q:
        term = f'%{q.strip()}%'
        filters.append(or_(Case.case_title.ilike(term), Case.case_number.ilike(term), Case.cnr_number.ilike(term),
            Case.court.has(Court.name.ilike(term)), Case.primary_client.has(Client.full_name.ilike(term)),
            Case.id.in_(select(CaseParty.case_id).join(Client, CaseParty.client_id == Client.id).where(CaseParty.user_id == user.id, Client.full_name.ilike(term)))))
    order = Case.case_title.asc() if sort == 'alphabetical' else Case.filing_date.desc() if sort == 'filing' else Case.updated_at.desc()
    total = db.scalar(select(func.count()).select_from(Case).where(*filters)) or 0
    items = db.scalars(select(Case).options(selectinload(Case.court), selectinload(Case.primary_client)).where(*filters).order_by(order, Case.id).offset(offset).limit(limit)).all()
    return total, [serialize(item) for item in items]

def party(db, user, case_id, party_id):
    owned_case(db, user, case_id, include_archived=True)
    item = db.scalar(select(CaseParty).where(CaseParty.id == party_id, CaseParty.case_id == case_id, CaseParty.user_id == user.id))
    if not item: raise HTTPException(404, 'Party not found')
    return item

def advocate(db, user, case_id, advocate_id):
    owned_case(db, user, case_id, include_archived=True)
    item = db.scalar(select(CaseAdvocate).where(CaseAdvocate.id == advocate_id, CaseAdvocate.case_id == case_id, CaseAdvocate.user_id == user.id))
    if not item: raise HTTPException(404, 'Advocate not found')
    return item

def mutate_party(db, user, case_id, data, party_id=None):
    item = owned_case(db, user, case_id, include_archived=True)
    if item.is_archived: raise HTTPException(409, 'Restore the case before editing parties')
    target = party(db, user, case_id, party_id) if party_id else None
    if target:
        values = data.model_dump()
        if data.client_id:
            client = check_client(db, user, data.client_id)
            values.update(party_name=client.full_name, party_type=client.client_type, address=client.address, phone_number=client.phone_number, email=client.email)
        for key, value in values.items(): setattr(target, key, value)
        log(db, user, item, 'case_party_updated', 'Party updated', details={'role': target.party_role})
    else: target = add_party_record(db, user, item, data)
    db.commit(); db.refresh(target)
    return target

def delete_party(db, user, case_id, party_id):
    item = owned_case(db, user, case_id, include_archived=True)
    if item.is_archived: raise HTTPException(409, 'Restore the case before editing parties')
    target = party(db, user, case_id, party_id)
    log(db, user, item, 'case_party_removed', 'Party removed', details={'role': target.party_role})
    db.delete(target); db.commit()

def mutate_advocate(db, user, case_id, data, advocate_id=None):
    item = owned_case(db, user, case_id, include_archived=True)
    if item.is_archived: raise HTTPException(409, 'Restore the case before editing advocates')
    target = advocate(db, user, case_id, advocate_id) if advocate_id else None
    if data.is_primary and db.scalar(select(CaseAdvocate.id).where(CaseAdvocate.case_id == case_id, CaseAdvocate.is_primary.is_(True), CaseAdvocate.id != (target.id if target else UUID(int=0)))):
        raise HTTPException(409, 'A primary advocate already exists')
    if target:
        for key, value in data.model_dump().items(): setattr(target, key, value)
        log(db, user, item, 'case_advocate_updated', 'Advocate representation updated', details={'role': data.representation_role})
    else: target = add_advocate_record(db, user, item, data)
    db.commit(); db.refresh(target)
    return target

def delete_advocate(db, user, case_id, advocate_id):
    item = owned_case(db, user, case_id, include_archived=True)
    if item.is_archived: raise HTTPException(409, 'Restore the case before editing advocates')
    target = advocate(db, user, case_id, advocate_id)
    if target.is_primary: raise HTTPException(409, 'Primary advocate cannot be removed')
    log(db, user, item, 'case_advocate_removed', 'Advocate representation removed', details={'role': target.representation_role})
    db.delete(target); db.commit()

def events(db, user, case_id, limit, offset, oldest=False, category=None, from_date=None, to_date=None):
    owned_case(db, user, case_id, include_archived=True)
    filters = [CaseActivity.case_id == case_id, CaseActivity.user_id == user.id]
    if category == 'case': filters.extend([CaseActivity.activity_type.like('case_%'), CaseActivity.activity_type != 'case_status_changed'])
    elif category == 'status': filters.append(CaseActivity.activity_type == 'case_status_changed')
    elif category == 'hearing': filters.append(CaseActivity.activity_type.like('hearing_%'))
    elif category == 'diary': filters.append(CaseActivity.activity_type.like('diary_%'))
    if from_date: filters.append(CaseActivity.created_at >= datetime.combine(from_date, datetime.min.time(), timezone.utc))
    if to_date: filters.append(CaseActivity.created_at < datetime.combine(to_date, datetime.min.time(), timezone.utc) + timedelta(days=1))
    total = db.scalar(select(func.count()).select_from(CaseActivity).where(*filters)) or 0
    order = (CaseActivity.created_at.asc(), CaseActivity.id.asc()) if oldest else (CaseActivity.created_at.desc(), CaseActivity.id.desc())
    return total, db.scalars(select(CaseActivity).where(*filters).order_by(*order).offset(offset).limit(limit)).all()

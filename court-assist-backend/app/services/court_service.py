from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from app.models.court import AdvocateCourtFavorite, Court
from app.models.user import User
from app.schemas.court import CourtCreate, CourtOut, CourtUpdate
from app.services.activity_service import record_activity


def visible_filter(user): return or_(Court.user_id.is_(None), Court.user_id == user.id)


def visible_court(db, user, court_id):
    court = db.scalar(select(Court).where(Court.id == court_id, Court.is_active.is_(True), visible_filter(user)))
    if not court: raise HTTPException(404, 'Court not found')
    return court


def serialize(court, favorite_ids, user):
    return CourtOut.model_validate({**court.__dict__, 'official_website': court.official_website, 'source': court.source,
        'record_scope': 'shared' if court.user_id is None else 'private', 'is_favorite': court.id in favorite_ids, 'can_edit': court.user_id == user.id})


def list_courts(db, user, limit, offset, q=None, court_type=None, district=None, state=None, favorites=False):
    filters = [Court.is_active.is_(True), visible_filter(user)]
    if q: filters.append(Court.name.ilike(f'%{q.strip()}%'))
    if court_type: filters.append(Court.court_type == court_type)
    if district: filters.append(func.lower(Court.district) == district.strip().lower())
    if state: filters.append(func.lower(Court.state) == state.strip().lower())
    query = select(Court).where(*filters)
    count_query = select(func.count()).select_from(Court).where(*filters)
    if favorites:
        query = query.join(AdvocateCourtFavorite, and_(AdvocateCourtFavorite.court_id == Court.id, AdvocateCourtFavorite.user_id == user.id))
        count_query = count_query.join(AdvocateCourtFavorite, and_(AdvocateCourtFavorite.court_id == Court.id, AdvocateCourtFavorite.user_id == user.id))
    total = db.scalar(count_query) or 0
    courts = db.scalars(query.order_by(Court.name.asc()).offset(offset).limit(limit)).all()
    favorite_ids = set(db.scalars(select(AdvocateCourtFavorite.court_id).where(AdvocateCourtFavorite.user_id == user.id)).all())
    return total, [serialize(c, favorite_ids, user) for c in courts]


def get_court(db, user, court_id):
    court = visible_court(db, user, court_id)
    favorites = set(db.scalars(select(AdvocateCourtFavorite.court_id).where(AdvocateCourtFavorite.user_id == user.id, AdvocateCourtFavorite.court_id == court.id)).all())
    return serialize(court, favorites, user)


def create_court(db, user, data: CourtCreate):
    values = data.model_dump(); values['official_website'] = str(values['official_website']) if values['official_website'] else None; values['source'] = str(values['source']) if values['source'] else None
    court = Court(user_id=user.id, **values); db.add(court); db.flush()
    record_activity(db, user.id, 'court_created', 'Custom court created', entity_type='court', entity_id=court.id)
    db.commit(); db.refresh(court); return serialize(court, set(), user)


def update_court(db, user, court_id, data: CourtUpdate):
    court = visible_court(db, user, court_id)
    if court.user_id != user.id: raise HTTPException(403, 'Shared courts cannot be modified')
    changes = data.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, 'Provide at least one field')
    for k, v in changes.items(): setattr(court, k, str(v) if k in ('official_website',) and v else v)
    db.commit(); db.refresh(court); return get_court(db, user, court.id)


def delete_court(db, user, court_id):
    court = visible_court(db, user, court_id)
    if court.user_id != user.id: raise HTTPException(403, 'Shared courts cannot be deleted')
    court.is_active = False; db.commit()


def favorite(db, user, court_id):
    visible_court(db, user, court_id)
    existing = db.scalar(select(AdvocateCourtFavorite).where(AdvocateCourtFavorite.user_id == user.id, AdvocateCourtFavorite.court_id == court_id))
    if not existing: db.add(AdvocateCourtFavorite(user_id=user.id, court_id=court_id)); db.commit()


def unfavorite(db, user, court_id):
    visible_court(db, user, court_id)
    item = db.scalar(select(AdvocateCourtFavorite).where(AdvocateCourtFavorite.user_id == user.id, AdvocateCourtFavorite.court_id == court_id))
    if item: db.delete(item); db.commit()

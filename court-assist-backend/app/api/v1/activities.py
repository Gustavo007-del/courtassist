from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.activity import ActivityPage
from app.services.activity_service import list_activities

router = APIRouter(prefix='/activities', tags=['activities'])


@router.get('', response_model=ActivityPage)
def activities(user: User = Depends(current_user), db: Session = Depends(get_db),
               limit: int = Query(default=20, ge=1, le=100),
               offset: int = Query(default=0, ge=0),
               activity_type: str | None = Query(default=None, max_length=64),
               from_date: date | None = None, to_date: date | None = None):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, 'from_date must not be after to_date')
    total, items = list_activities(db, user, limit, offset, activity_type, from_date, to_date)
    return ActivityPage(items=items, total=total, limit=limit, offset=offset)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import overview

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


@router.get('/overview', response_model=DashboardOut)
def dashboard_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return overview(db, user)

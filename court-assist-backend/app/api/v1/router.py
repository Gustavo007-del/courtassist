from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.v1 import activities, auth, cases, clients, courts, dashboard, diary, hearings, users
from app.database.session import get_db

router = APIRouter(prefix='/api/v1')
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(dashboard.router)
router.include_router(activities.router)
router.include_router(clients.router)
router.include_router(courts.router)
router.include_router(cases.router)
router.include_router(hearings.router)
router.include_router(diary.router)


@router.get('/health', tags=['system'])
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'ok'}

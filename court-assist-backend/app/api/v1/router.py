from fastapi import APIRouter, Depends, HTTPException
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.v1 import activities, auth, cases, clients, courts, dashboard, diary, documents, hearings, planning, users, phase10, finance
from app.database.session import get_db
from app.api.v1.rate_limit import redis_client
from app.core.config import get_settings
from app.api.v1 import drafting, research
from app.api.v1 import ai, sync

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
router.include_router(documents.router)
router.include_router(planning.router)
router.include_router(phase10.router)
router.include_router(finance.router)
router.include_router(drafting.router)
router.include_router(research.router)
router.include_router(ai.router)
router.include_router(sync.router)


@router.get('/health', tags=['system'])
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'ok'}


@router.get('/live', tags=['system'])
def live():
    return {'status': 'ok'}


@router.get('/ready', tags=['system'])
def ready(db: Session = Depends(get_db)):
    settings = get_settings()
    db.execute(text('SELECT 1'))
    if settings.hardened and db.scalar(text('SELECT version_num FROM alembic_version')) != '0021_release_controls':
        raise HTTPException(503, 'Service is not ready')
    if settings.redis_url:
        try:
            redis_client(settings.redis_url).ping()
        except RedisError:
            raise HTTPException(503, 'Service is not ready') from None
    return {'status': 'ok'}

from app.api.v1 import notifications
router.include_router(notifications.router)

import logging
from celery import Celery
from sqlalchemy import select
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.user import User,UserPreference
from app.models.notifications import NotificationEvent
from app.services.notification_service import reconcile_user
from app.services.notification_delivery import dispatch

from app.services.notification_events import install
install()

celery_app=Celery('court_assist_notifications',broker=get_settings().redis_url)
celery_app.conf.update(task_default_queue='court-assist-notifications',task_ignore_result=True,
    task_acks_late=True,worker_prefetch_multiplier=1,task_reject_on_worker_lost=True,
    beat_schedule={'recover-and-dispatch-notifications':{'task':'app.workers.notifications.tick','schedule':60.0}})
celery_app.conf.beat_schedule['process-optional-ai'] = {
    'task': 'app.workers.ocr.drain_ai',
    'schedule': 15.0,
    'options': {'queue': 'court-assist-ai', 'expires': 14},
}

@celery_app.task(name='app.workers.notifications.tick')
def tick():
    with SessionLocal() as db:
        events=db.scalars(select(NotificationEvent.user_id).where(NotificationEvent.processed_at.is_(None)).distinct().limit(100)).all()
        background=db.scalars(select(User.id).outerjoin(UserPreference,UserPreference.user_id==User.id).where(User.is_active.is_(True)).order_by(UserPreference.notification_checked_at.asc().nulls_first(),User.id).limit(100)).all()
        for identifier in dict.fromkeys([*events,*background]):
            user=db.get(User,identifier)
            if user and user.is_active:
                try:reconcile_user(db,user);db.commit()
                except Exception:
                    db.rollback() # Leave durable events pending for the next tick.
                    logging.getLogger(__name__).warning('Notification reconciliation failed; pending events retained')
        return dispatch(db)

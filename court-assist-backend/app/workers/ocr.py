from celery import Celery
from app.core.config import get_settings
from app.services.document_ocr import process_ocr

celery_app = Celery('court_assist_ocr', broker=get_settings().redis_url)
celery_app.conf.update(task_default_queue='court-assist-ocr', worker_prefetch_multiplier=1,
                      broker_connection_retry_on_startup=True, task_ignore_result=True)


@celery_app.task(name='app.workers.ocr.process_document_ocr', soft_time_limit=540, time_limit=600)
def process_document_ocr(ocr_id: str):
    process_ocr(ocr_id)


@celery_app.task(name='app.workers.ocr.drain_ai', soft_time_limit=2400, time_limit=2460, ignore_result=True)
def drain_ai():
    from app.database.session import SessionLocal
    from app.services import ai_jobs

    with SessionLocal() as db:
        ai_jobs.sweep(db)
        identifier = ai_jobs.claim(db)
    if identifier:
        ai_jobs.process(identifier)

"""Consent, durable queue lifecycle, quota accounting and retention."""

import hashlib
import json
from datetime import timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.ai import AIChunk, AIConversation, AIJob, AIPreference, utcnow
from app.models.user import User
from app.services.ai_context import owned
from app.services.ai_generation import generate
from app.services.ai_provider import AIError, configured_provider


ACTIVE = ("pending", "processing")
PREFERENCE_FIELDS = ("enabled", "documents", "assistant", "external", "retention_days")


def lock_user(db, owner):
    db.execute(select(User.id).where(User.id == owner).with_for_update()).scalar_one()


def preferences(db, owner, lock=False):
    query = select(AIPreference).where(AIPreference.user_id == owner)
    return db.scalar(query.with_for_update() if lock else query)


def consent_error(prefs, provider, request, kind, revision=None):
    if not prefs or not prefs.enabled:
        return "ai_disabled"
    if revision is not None and prefs.revision != revision:
        return "consent_changed"
    if not provider:
        return "provider_unconfigured"
    if (kind in ("summarize", "dates", "metadata") or any(
        source["kind"] == "document" for source in request.get("sources", ())
    )) and not prefs.documents:
        return "document_consent_required"
    if kind in ("ask", "chronology") and not prefs.assistant:
        return "assistant_consent_required"
    if provider.external and (
        not prefs.external or prefs.provider_consent != provider.fingerprint
        or request.get("external_confirmation") != provider.fingerprint
    ):
        return "external_consent_required"
    return None


def find_job(db, owner, identifier, lock=False):
    query = select(AIJob).where(
        AIJob.id == identifier, AIJob.user_id == owner, AIJob.deleted_at.is_(None), AIJob.expires_at > utcnow(),
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(404, "AI job not found")
    return row


def submit(db, user, kind, payload, case_id=None, document_id=None, draft_id=None, conversation_id=None, make_conversation=False):
    lock_user(db, user.id)
    prefs = preferences(db, user.id)
    provider = configured_provider()
    error = consent_error(prefs, provider, payload, kind)
    if error:
        raise HTTPException(503 if error == "provider_unconfigured" else 403, error)
    settings = get_settings()
    if not settings.redis_url:
        raise HTTPException(503, "worker_unconfigured")
    identifier = UUID(payload.pop("request_id"))
    digest = hashlib.sha256(json.dumps(
        [kind, payload, str(case_id), str(document_id), str(draft_id), str(conversation_id)],
        sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    existing = db.scalar(select(AIJob).where(AIJob.user_id == user.id, AIJob.request_id == identifier))
    if existing:
        if existing.request_digest != digest or existing.deleted_at:
            raise HTTPException(409, "request_id_already_used")
        return existing
    now = utcnow()
    for duration, limit in (
        (timedelta(minutes=1), settings.ai_requests_per_minute),
        (timedelta(days=1), settings.ai_requests_per_day),
    ):
        used = db.scalar(select(func.count()).select_from(AIJob).where(
            AIJob.user_id == user.id, AIJob.created_at >= now - duration,
        ))
        if used >= limit:
            raise HTTPException(429, "ai_request_limit")
    if conversation_id:
        owned(db, AIConversation, user.id, conversation_id)
    elif make_conversation:
        conversation = AIConversation(user_id=user.id)
        db.add(conversation)
        db.flush()
        conversation_id = conversation.id
    job = AIJob(
        user_id=user.id, request_id=identifier, request_digest=digest, kind=kind, case_id=case_id,
        document_id=document_id, draft_id=draft_id, conversation_id=conversation_id,
        provider=provider.name, model=provider.model, provider_fingerprint=provider.fingerprint,
        consent_revision=prefs.revision, request_data=payload, expires_at=now + timedelta(days=prefs.retention_days),
    )
    db.add(job)
    db.commit()
    return job


def cancel(job, code="cancelled"):
    job.status = "cancelled"
    job.error_code = code
    job.lease_until = None
    job.completed_at = utcnow()
    job.request_data = None


def erase(db, job, now):
    if job.status in ACTIVE:
        cancel(job)
    db.execute(delete(AIChunk).where(AIChunk.job_id == job.id, AIChunk.user_id == job.user_id))
    job.request_data = job.result = job.review = job.approval = None
    job.request_digest = None
    job.conversation_id = job.case_id = job.document_id = job.draft_id = None
    job.deleted_at = now


def claim(db):
    now = utcnow()
    job = db.scalar(select(AIJob).where(
        AIJob.status == "pending", AIJob.available_at <= now, AIJob.expires_at > now, AIJob.deleted_at.is_(None),
    ).order_by(AIJob.available_at, AIJob.id).limit(1).with_for_update(skip_locked=True))
    if not job:
        return None
    job.status = "processing"
    job.attempts += 1
    job.started_at = now
    job.lease_until = now + timedelta(minutes=45)
    db.commit()
    return job.id


def verify_processing(job, prefs, provider):
    if not job or job.status != "processing" or job.deleted_at or not job.request_data:
        raise AIError("cancelled")
    if job.expires_at.replace(tzinfo=job.expires_at.tzinfo or timezone.utc) <= utcnow():
        raise AIError("retention_expired")
    error = consent_error(prefs, provider, job.request_data, job.kind, job.consent_revision)
    if error:
        raise AIError(error)
    if provider.fingerprint != job.provider_fingerprint:
        raise AIError("provider_changed")


def process(identifier):
    provider = configured_provider()
    successful_calls = 0

    def call(method, *args):
        nonlocal successful_calls
        with SessionLocal() as db:
            current = db.get(AIJob, identifier)
            if not current:
                raise AIError("cancelled")
            # Consent changes serialize against each outbound call. An already-sent request cannot be recalled.
            prefs = preferences(db, current.user_id, lock=True)
            db.refresh(current)
            verify_processing(current, prefs, provider)
            if not db.scalar(select(User.is_active).where(User.id == current.user_id)):
                raise AIError("ai_disabled")
            value, usage = method(*args)
            successful_calls += 1
            db.refresh(current, with_for_update=True)
            if usage.input_tokens is not None:
                current.input_tokens = (current.input_tokens or 0) + usage.input_tokens
            if usage.output_tokens is not None:
                current.output_tokens = (current.output_tokens or 0) + usage.output_tokens
            settings = provider.settings
            if settings.ai_input_cost_per_million is not None and settings.ai_output_cost_per_million is not None:
                current.estimated_cost = (
                    (current.input_tokens or 0) * settings.ai_input_cost_per_million
                    + (current.output_tokens or 0) * settings.ai_output_cost_per_million
                ) / 1_000_000 if current.input_tokens is not None or current.output_tokens is not None else None
            db.commit()
            return value

    failure = None
    chunks = []
    result = None
    try:
        with SessionLocal() as db:
            job = db.get(AIJob, identifier)
            if not job:
                return
            verify_processing(job, preferences(db, job.user_id), provider)
            # Detach the metadata so document reads don't hold a database transaction during provider calls.
            db.expunge(job)
            db.rollback()
            result, chunks = generate(db, job, provider, call)
    except AIError as error:
        failure = error
    except HTTPException:
        failure = AIError("source_unavailable")
    except Exception:
        failure = AIError("processing_failed")
    with SessionLocal() as db:
        job = db.scalar(select(AIJob).where(AIJob.id == identifier).with_for_update())
        if not job or job.status != "processing":
            return
        now = utcnow()
        job.lease_until = None
        if failure and failure.retryable and not successful_calls and job.attempts < 3:
            job.status = "pending"
            job.error_code = failure.code
            job.available_at = now + timedelta(seconds=30 * 2 ** (job.attempts - 1))
        elif failure:
            job.status = "failed"
            job.error_code = failure.code
            job.completed_at = now
        else:
            job.status = "completed"
            job.error_code = None
            job.completed_at = now
            job.result = result
            db.add_all(chunks)
        db.commit()


def sweep(db):
    now = utcnow()
    expired = db.scalars(select(AIJob).where(
        AIJob.deleted_at.is_(None), AIJob.expires_at <= now,
    ).limit(100).with_for_update(skip_locked=True)).all()
    for job in expired:
        erase(db, job, now)
    stale = db.scalars(select(AIJob).where(
        AIJob.status == "processing", AIJob.lease_until <= now,
    ).limit(100).with_for_update(skip_locked=True)).all()
    for job in stale:
        job.status = "failed"
        job.error_code = "worker_interrupted"
        job.completed_at = now
        job.lease_until = None
    db.flush()
    db.execute(delete(AIConversation).where(~select(AIJob.id).where(
        AIJob.conversation_id == AIConversation.id, AIJob.user_id == AIConversation.user_id,
    ).exists()))
    db.commit()


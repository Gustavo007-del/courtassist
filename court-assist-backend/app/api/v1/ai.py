"""Authenticated, owner-scoped Phase 14 routes."""

from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import current_user
from app.core.config import get_settings
from app.database.session import get_db
from app.models.ai import AIConversation, AIJob, AIPreference, utcnow
from app.models.case import Case
from app.models.diary import CaseDiaryEntry
from app.models.phase10 import DraftDocument
from app.models.user import User
from app.schemas.ai import (
    Ask, DiaryApproval, DiaryWriting, DraftApproval, PreferencesPatch, Review, ScopedSubmission,
    SourceKind, SourceSelection, Submission, Writing,
)
from app.services import ai_context, ai_jobs, ai_review
from app.services.ai_provider import configured_provider


class PrivateAIRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                response = await handler(request)
            except RequestValidationError:
                # FastAPI's default 422 includes rejected values, which can contain confidential text.
                response = JSONResponse(status_code=422, content={"detail": "invalid_ai_request"})
            response.headers['Cache-Control'] = 'no-store'
            return response

        return handle


router = APIRouter(prefix="/ai", tags=["optional AI"], route_class=PrivateAIRoute)
DB = Annotated[Session, Depends(get_db)]
Advocate = Annotated[User, Depends(current_user)]
Limit = Annotated[int, Query(ge=1, le=50)]
Offset = Annotated[int, Query(ge=0, le=10000)]
SUMMARY_FIELDS = (
    "id", "kind", "status", "provider", "model", "attempts", "error_code", "case_id",
    "document_id", "draft_id", "conversation_id", "created_at", "started_at", "completed_at", "expires_at",
    "input_tokens", "output_tokens", "estimated_cost",
)


def serialize(job, detail=False):
    fields = {field: getattr(job, field) for field in SUMMARY_FIELDS}
    if detail:
        payload = job.request_data or {}
        fields.update(
            result=job.result, review=job.review, approval=job.approval,
            question=payload.get("question"), selected_text=payload.get("text"),
            sources=payload.get("sources", []), draft_revision=payload.get("draft_revision"),
            can_retry=job.status == "failed" and bool(payload),
        )
    return fields


def active_rows(user):
    return select(AIJob).where(
        AIJob.user_id == user.id, AIJob.deleted_at.is_(None), AIJob.expires_at > utcnow(),
    )


def page(db, statement, offset, limit, detail=False):
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = db.scalars(statement.order_by(AIJob.created_at.desc(), AIJob.id.desc()).offset(offset).limit(limit))
    return {"items": [serialize(row, detail) for row in rows], "total": total}


def preference_view(prefs):
    provider = configured_provider()
    defaults = PreferencesPatch()
    values = {field: getattr(prefs or defaults, field) for field in ai_jobs.PREFERENCE_FIELDS}
    if provider and provider.external and (not prefs or prefs.provider_consent != provider.fingerprint):
        values["external"] = False
    return {
        **values,
        "available": bool(provider and get_settings().redis_url),
        "provider": provider.name if provider else None,
        "model": provider.model if provider else None,
        "embeddings_available": bool(provider and get_settings().ai_embedding_model),
        "external_provider": bool(provider and provider.external),
        "provider_policy": get_settings().ai_provider_policy if provider and provider.external else None,
        "external_confirmation": provider.fingerprint if provider and provider.external else None,
    }


@router.get("/preferences")
def get_preferences(db: DB, user: Advocate):
    return preference_view(ai_jobs.preferences(db, user.id))


@router.patch("/preferences")
def patch_preferences(data: PreferencesPatch, db: DB, user: Advocate):
    ai_jobs.lock_user(db, user.id)
    prefs = ai_jobs.preferences(db, user.id, lock=True)
    if prefs is None:
        prefs = AIPreference(user_id=user.id)
        db.add(prefs)
        db.flush()
    changes = data.model_dump(exclude_unset=True, exclude={"external_confirmation"})
    if changes.get("external"):
        provider = configured_provider()
        if not provider or not provider.external or provider.fingerprint != data.external_confirmation:
            raise HTTPException(422, "external_consent_required")
        changes["provider_consent"] = provider.fingerprint
    elif changes.get("external") is False:
        changes["provider_consent"] = None
    invalidate = any(field != "retention_days" and getattr(prefs, field) != value for field, value in changes.items())
    for field, value in changes.items():
        setattr(prefs, field, value)
    if invalidate:
        prefs.revision += 1
        rows = db.scalars(active_rows(user).where(AIJob.status.in_(ai_jobs.ACTIVE)).with_for_update()).all()
        for row in rows:
            ai_jobs.cancel(row, "consent_changed")
    if "retention_days" in changes:
        # Shorten existing records where applicable. Extending the setting applies to new jobs.
        cutoff = utcnow() - timedelta(days=prefs.retention_days)
        from sqlalchemy import update
        expiry = utcnow()
        db.execute(update(AIJob).where(
            AIJob.user_id == user.id, AIJob.deleted_at.is_(None), AIJob.created_at <= cutoff,
        ).values(expires_at=expiry))
        # Intermediate ages must also get the new upper bound.
        future_rows = db.scalars(active_rows(user)).all()
        for row in future_rows:
            expires = row.created_at + timedelta(days=prefs.retention_days)
            if ai_review.revision(expires) < ai_review.revision(row.expires_at):
                row.expires_at = expires
    db.commit()
    return preference_view(prefs)


@router.get("/context")
def context(kind: SourceKind, db: DB, user: Advocate, case_id: UUID | None = None, offset: Offset = 0, limit: Limit = 30):
    if case_id:
        ai_context.owned(db, Case, user.id, case_id)
    model = ai_context.MODELS[kind]
    query = select(model).where(model.user_id == user.id)
    if case_id and kind != "research":
        column = model.id if kind == "case" else model.case_id
        query = query.where(column == case_id)
    if hasattr(model, "is_archived"):
        query = query.where(model.is_archived.is_(False))
    if hasattr(model, "archived_at"):
        query = query.where(model.archived_at.is_(None))
    if kind == "document":
        query = query.where(model.current_version_id.is_not(None))
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(model.created_at.desc(), model.id.desc()).offset(offset).limit(limit))
    return {"items": [{
        "kind": kind, "id": row.id,
        "title": next((value for attr in ("case_title", "document_name", "title", "purpose", "new_status")
                       if (value := getattr(row, attr, None))), kind),
        "date": getattr(row, "hearing_date", getattr(row, "entry_date", getattr(row, "effective_date", None))),
    } for row in rows], "total": count}


def scoped(db, user, data, case_id):
    if case_id:
        ai_context.owned(db, Case, user.id, case_id)
    payload = data.model_dump(mode="json")
    payload["sources"] = ai_context.pin_sources(db, user.id, payload["sources"], case_id)
    return payload


def ask_job(data, db, user, conversation_id=None):
    payload = scoped(db, user, data, data.case_id)
    previous_id = payload.pop("previous_job_id", None)
    if previous_id:
        previous = ai_jobs.find_job(db, user.id, UUID(previous_id))
        if not conversation_id or previous.conversation_id != conversation_id or not previous.request_data:
            raise HTTPException(404, "Previous message not found")
        payload["previous_question"] = previous.request_data.get("question")
    return serialize(ai_jobs.submit(
        db, user, "ask", payload, case_id=data.case_id, conversation_id=conversation_id,
        make_conversation=conversation_id is None,
    ))


@router.post("/ask", status_code=202)
def ask(data: Ask, db: DB, user: Advocate):
    return ask_job(data, db, user)


@router.get("/conversations")
def conversations(db: DB, user: Advocate, offset: Offset = 0, limit: Limit = 30):
    rows = db.scalars(select(AIConversation).where(
        AIConversation.user_id == user.id,
        active_rows(user).where(AIJob.conversation_id == AIConversation.id).exists(),
    ).order_by(AIConversation.created_at.desc(), AIConversation.id.desc()).offset(offset).limit(limit))
    return {"items": [{"id": row.id, "created_at": row.created_at} for row in rows]}


@router.get("/conversations/{identifier}")
def conversation(identifier: UUID, db: DB, user: Advocate, offset: Offset = 0, limit: Limit = 30):
    ai_context.owned(db, AIConversation, user.id, identifier)
    return page(db, active_rows(user).where(AIJob.conversation_id == identifier), offset, limit, detail=True)


@router.post("/conversations/{identifier}/messages", status_code=202)
def message(identifier: UUID, data: Ask, db: DB, user: Advocate):
    ai_context.owned(db, AIConversation, user.id, identifier)
    return ask_job(data, db, user, identifier)


@router.delete("/conversations/{identifier}", status_code=204)
def delete_conversation(identifier: UUID, db: DB, user: Advocate):
    ai_jobs.lock_user(db, user.id)
    row = ai_context.owned(db, AIConversation, user.id, identifier, lock=True)
    jobs = db.scalars(select(AIJob).where(
        AIJob.user_id == user.id, AIJob.conversation_id == identifier,
    ).with_for_update()).all()
    for job in jobs:
        ai_jobs.erase(db, job, utcnow())
    db.flush()
    db.delete(row)
    db.commit()


class DocumentRequest(Submission):
    first_page: int | None = None
    last_page: int | None = None


@router.post("/documents/{identifier}/{operation}", status_code=202)
def document_job(identifier: UUID, operation: Literal["summarize", "extract-dates", "extract-metadata"], data: DocumentRequest, db: DB, user: Advocate):
    from pydantic import ValidationError
    try:
        source = SourceSelection(kind="document", id=identifier, first_page=data.first_page, last_page=data.last_page)
    except ValidationError:
        raise HTTPException(422, "invalid_page_range") from None
    doc = ai_context.resolve(db, user.id, source.model_dump(mode="json"), None)
    payload = data.model_dump(mode="json", exclude={"first_page", "last_page"})
    payload["sources"] = ai_context.pin_sources(db, user.id, [source.model_dump(mode="json")], doc.case_id)
    kind = {"summarize": "summarize", "extract-dates": "dates", "extract-metadata": "metadata"}[operation]
    return serialize(ai_jobs.submit(db, user, kind, payload, case_id=doc.case_id, document_id=identifier))


@router.get("/documents/{identifier}/results")
def document_results(identifier: UUID, db: DB, user: Advocate, offset: Offset = 0, limit: Limit = 30):
    ai_context.owned(db, ai_context.MODELS["document"], user.id, identifier)
    return page(db, active_rows(user).where(AIJob.document_id == identifier), offset, limit)


@router.post("/cases/{identifier}/chronology", status_code=202)
def chronology(identifier: UUID, data: ScopedSubmission, db: DB, user: Advocate):
    return serialize(ai_jobs.submit(db, user, "chronology", scoped(db, user, data, identifier), case_id=identifier))


@router.get("/cases/{identifier}/chronology/{job_id}")
def chronology_result(identifier: UUID, job_id: UUID, db: DB, user: Advocate):
    ai_context.owned(db, Case, user.id, identifier)
    job = ai_jobs.find_job(db, user.id, job_id)
    if job.kind != "chronology" or job.case_id != identifier:
        raise HTTPException(404, "Chronology not found")
    return serialize(job, True)


@router.post("/drafts/{identifier}/{operation}", status_code=202)
def draft_job(identifier: UUID, operation: Literal["improve", "rewrite", "organize", "summarize", "translate"], data: Writing, db: DB, user: Advocate):
    draft = ai_context.owned(db, DraftDocument, user.id, identifier)
    if draft.archived_at:
        raise HTTPException(409, "draft_archived")
    if draft.case_id:
        ai_context.owned(db, Case, user.id, draft.case_id)
    payload = data.model_dump(mode="json")
    payload.update(action=operation, draft_revision=ai_review.revision(draft.updated_at))
    return serialize(ai_jobs.submit(db, user, "draft", payload, case_id=draft.case_id, draft_id=identifier))


@router.post("/diary/organize", status_code=202)
def diary_job(data: DiaryWriting, db: DB, user: Advocate):
    case_id = data.case_id
    if data.entry_id:
        row = ai_context.owned(db, CaseDiaryEntry, user.id, data.entry_id)
        if case_id and row.case_id != case_id:
            raise HTTPException(422, "case_does_not_match")
        case_id = row.case_id
    if case_id:
        ai_context.owned(db, Case, user.id, case_id)
    return serialize(ai_jobs.submit(db, user, "diary", data.model_dump(mode="json"), case_id=case_id))


@router.get("/jobs")
def jobs(db: DB, user: Advocate, offset: Offset = 0, limit: Limit = 30):
    return page(db, active_rows(user), offset, limit)


@router.get("/jobs/{identifier}")
def detail(identifier: UUID, db: DB, user: Advocate):
    return serialize(ai_jobs.find_job(db, user.id, identifier), True)


@router.post("/jobs/{identifier}/cancel")
def cancel(identifier: UUID, db: DB, user: Advocate):
    job = ai_jobs.find_job(db, user.id, identifier, lock=True)
    if job.status in ai_jobs.ACTIVE:
        ai_jobs.cancel(job)
        db.commit()
    return serialize(job)


@router.post("/jobs/{identifier}/retry", status_code=202)
def retry(identifier: UUID, data: Submission, db: DB, user: Advocate):
    job = ai_jobs.find_job(db, user.id, identifier)
    if job.status != "failed" or not job.request_data:
        raise HTTPException(409, "job_not_retryable")
    payload = {**job.request_data, "request_id": str(data.request_id), "external_confirmation": data.external_confirmation}
    return serialize(ai_jobs.submit(
        db, user, job.kind, payload, job.case_id, job.document_id, job.draft_id, job.conversation_id,
    ))


@router.delete("/jobs/{identifier}", status_code=204)
def erase(identifier: UUID, db: DB, user: Advocate):
    job = ai_jobs.find_job(db, user.id, identifier, lock=True)
    ai_jobs.erase(db, job, utcnow())
    db.commit()


@router.patch("/jobs/{identifier}/review")
def review(identifier: UUID, data: Review, db: DB, user: Advocate):
    job = ai_jobs.find_job(db, user.id, identifier, lock=True)
    ai_review.require_result(job)
    job.review = {"text": data.text, "reviewed_at": utcnow().isoformat()}
    db.commit()
    return serialize(job, True)


@router.get("/jobs/{identifier}/export")
def export(identifier: UUID, db: DB, user: Advocate):
    job = ai_jobs.find_job(db, user.id, identifier)
    if job.kind != "chronology" or not job.review:
        raise HTTPException(409, "review_chronology_before_export")
    return PlainTextResponse(job.review["text"], headers={
        "Content-Disposition": 'attachment; filename="reviewed-chronology.txt"', "Cache-Control": "no-store",
    })


@router.post("/jobs/{identifier}/approve-draft")
def approve_draft(identifier: UUID, data: DraftApproval, db: DB, user: Advocate):
    return ai_review.approve_draft(db, user, ai_jobs.find_job(db, user.id, identifier, lock=True), data)


@router.post("/jobs/{identifier}/approve-diary")
def approve_diary(identifier: UUID, data: DiaryApproval, db: DB, user: Advocate):
    return ai_review.approve_diary(db, user, ai_jobs.find_job(db, user.id, identifier, lock=True), data)


@router.get("/usage")
def usage(db: DB, user: Advocate, offset: Offset = 0, limit: Limit = 30):
    query = select(AIJob).where(AIJob.user_id == user.id)
    rows = db.scalars(query.order_by(AIJob.created_at.desc(), AIJob.id.desc()).offset(offset).limit(limit))
    return {"items": [{field: getattr(row, field) for field in (
        "id", "kind", "status", "provider", "model", "created_at", "input_tokens", "output_tokens", "estimated_cost",
    )} for row in rows], "total": db.scalar(select(func.count()).select_from(query.subquery()))}


@router.get("/usage/summary")
def usage_summary(db: DB, user: Advocate):
    now = utcnow()
    totals = db.execute(select(
        func.count(), func.sum(AIJob.input_tokens), func.sum(AIJob.output_tokens), func.sum(AIJob.estimated_cost),
    ).where(AIJob.user_id == user.id, AIJob.created_at >= now - timedelta(days=1))).one()
    return dict(zip(("requests", "input_tokens", "output_tokens", "estimated_cost"), totals)) | {
        "daily_limit": get_settings().ai_requests_per_day, "window_hours": 24,
    }


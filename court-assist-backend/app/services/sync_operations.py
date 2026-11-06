"""Replay allow-listed operations through the existing business rules."""

import hashlib
import json
from datetime import timezone
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.v1 import documents, finance, hearings, phase10, planning
from app.models.sync import SyncOperation
from app.models.user import User
from app.schemas.case import CaseCreate, CaseUpdate, StatusChange
from app.schemas.diary import DiaryCreate, DiaryUpdate
from app.schemas.document import DocumentCreate, DocumentPatch
from app.schemas.finance import PaymentMetadata
from app.schemas.hearing import HearingCreate, HearingUpdate, Reschedule
from app.schemas.planning import AppointmentInput, AppointmentPatch, TaskInput, TaskPatch
from app.schemas.practice import DraftInput, DraftPatch, PaymentInput
from app.services import case_service, diary_service, hearing_service, planning_service, sync_feed as feed


def fields(schema, payload):
    if set(payload) - set(schema.model_fields):
        raise HTTPException(422, "unsupported_fields")
    return schema.model_validate(payload)


def empty(payload):
    if payload:
        raise HTTPException(422, "unexpected_payload")


def appointment_check(db, user, operation, data):
    if operation.action == "update":
        row = planning_service.appointment_owned(db, user, operation.entity_id)
        data = AppointmentInput.model_validate({
            **{key: getattr(row, key) for key in AppointmentInput.model_fields},
            **data.model_dump(exclude_unset=True),
        })
    if data.status == "Scheduled" and planning_service.appointment_conflicts(
        db, user, data.appointment_date, data.start_time, data.end_time,
        operation.entity_id if operation.action == "update" else None,
    ):
        raise HTTPException(409, "schedule_conflict")


def dispatch(db, user, operation):
    kind, action, identifier, payload = operation.kind, operation.action, operation.entity_id, operation.payload
    db.info["sync_record_id"] = identifier
    if kind == "case":
        if action == "create":
            return case_service.create_case(db, user, fields(CaseCreate, payload))
        if action == "update":
            return case_service.update_case(db, user, identifier, fields(CaseUpdate, payload))
        if action == "status":
            return case_service.change_status(db, user, identifier, fields(StatusChange, payload))
        if action in ("archive", "restore"):
            empty(payload)
            return case_service.set_archive(db, user, identifier, action == "archive")
    elif kind == "hearing":
        if action == "create":
            return hearings.create(fields(HearingCreate, payload), user=user, db=db)
        if action == "update":
            return hearing_service.update(db, user, identifier, fields(HearingUpdate, payload))
        if action == "cancel":
            empty(payload)
            return hearing_service.remove(db, user, identifier)
        if action == "reschedule":
            data = dict(payload)
            db.info["sync_followup_id"] = UUID(data.pop("follow_up_id"))
            return hearing_service.reschedule(db, user, identifier, fields(Reschedule, data))
    elif kind == "diary":
        if action == "create":
            return diary_service.create(db, user, fields(DiaryCreate, payload))
        if action == "update":
            return diary_service.update(db, user, identifier, fields(DiaryUpdate, payload))
        if action == "delete":
            empty(payload)
            return diary_service.delete(db, user, identifier)
        if action in ("pin", "unpin", "important", "unimportant"):
            empty(payload)
            return diary_service.flag(db, user, identifier, "is_pinned" if action.endswith("pin") else "is_important",
                                      action in ("pin", "important"))
    elif kind == "task":
        if action == "create":
            return planning.create_task(fields(TaskInput, payload), user=user, db=db)
        if action == "update":
            return planning.patch_task(identifier, fields(TaskPatch, payload), user=user, db=db)
        actions = {"complete": planning.complete_task, "archive": planning.archive_task, "reopen": planning.reopen_task}
        if action in actions:
            empty(payload)
            return actions[action](identifier, user=user, db=db)
    elif kind == "appointment":
        if action == "create":
            data = fields(AppointmentInput, payload)
            appointment_check(db, user, operation, data)
            return planning.create_appointment(data, user=user, db=db)
        if action == "update":
            data = fields(AppointmentPatch, payload)
            appointment_check(db, user, operation, data)
            return planning.patch_appointment(identifier, data, user=user, db=db)
        if action in ("cancel", "archive"):
            empty(payload)
            method = planning.cancel_appointment if action == "cancel" else planning.archive_appointment
            return method(identifier, user=user, db=db)
    elif kind == "document":
        if action == "create":
            return documents.create_document(fields(DocumentCreate, payload), user=user, db=db)
        if action == "update":
            return documents.patch_document(identifier, fields(DocumentPatch, payload), user=user, db=db)
        if action == "archive":
            empty(payload)
            return documents.delete_document(identifier, user=user, db=db)
    elif kind == "draft":
        if action == "create":
            return phase10.create_draft(fields(DraftInput, payload), user=user, db=db)
        if action == "update":
            # The sync revision supplies the concurrency check for these writes.
            return phase10.update_draft(identifier, fields(DraftPatch, payload), user=user, db=db)
        if action in ("archive", "restore"):
            empty(payload)
            method = phase10.archive_draft if action == "archive" else phase10.restore_draft
            return method(identifier, user=user, db=db)
    elif kind == "payment":
        if action == "create":
            data = fields(PaymentInput, {**payload, "status": "pending"})
            return phase10.add_payment(data, user=user, db=db, idempotency_key=f"sync-{identifier}")
        if action == "update":
            return finance.edit_payment_metadata(identifier, fields(PaymentMetadata, payload), user=user, db=db)
    raise HTTPException(422, "unsupported_operation")


def response(row):
    return {
        "id": str(row.id), "status": row.status, "kind": row.kind, "entity_id": str(row.entity_id),
        "revision": str(row.revision) if row.revision is not None else None, "server": row.server_record,
        "error": row.error, "resolved": row.resolution,
    }


def result_for(db, user, row):
    result = response(row)
    if row.status == "applied":
        feed.record(db, user.id, row.kind, row.entity_id, lock=True)
        result["server"] = feed.snapshot(db, user, row.kind, row.entity_id)
    return result


def ensure_transaction(db):
    if db.bind.dialect.name == "sqlite":
        conn = db.connection()
        if not conn.connection.driver_connection.in_transaction:
            conn.execute(text("BEGIN IMMEDIATE"))


def same_stamp(expected, actual):
    if expected is None:
        return True
    if actual is None:
        return False
    return expected.replace(tzinfo=expected.tzinfo or timezone.utc) == actual.replace(tzinfo=actual.tzinfo or timezone.utc)


def execute(db, user, device_id, operation, *, commit=True):
    ensure_transaction(db)
    owner = user.id
    feed.advisory_lock(db, f"courtassist-sync-op:{owner}:{operation.id}")
    payload = operation.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(encoded.encode()) > 1_000_000:
        return {"id": str(operation.id), "status": "invalid", "error": "operation_too_large"}
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    existing = db.get(SyncOperation, (owner, operation.id))
    if existing:
        return result_for(db, user, existing) if existing.digest == digest else {
            "id": str(operation.id), "status": "invalid", "error": "operation_id_reused",
        }
    base = int(operation.base_revision)
    for dependency in set(operation.depends_on + ([operation.after_operation_id] if operation.after_operation_id else [])):
        prior = db.get(SyncOperation, (owner, dependency))
        resolved = prior.resolution if prior and prior.resolved_at else None
        accepted = resolved and resolved["strategy"] in ("local", "merge")
        if not prior or (prior.status != "applied" and not accepted):
            return {"id": str(operation.id), "status": "blocked", "error": "dependency_pending"}
        if dependency == operation.after_operation_id:
            if prior.kind != operation.kind or prior.entity_id != operation.entity_id:
                return {"id": str(operation.id), "status": "invalid", "error": "invalid_predecessor"}
            base = int(resolved["result"]["revision"]) if accepted else prior.revision
    if operation.kind == "appointment":
        feed.advisory_lock(db, f"courtassist-appointments:{owner}")
    row = feed.record(db, owner, operation.kind, operation.entity_id, lock=True)
    revision = feed.version(db, owner, operation.kind, operation.entity_id)
    status, error = "applied", None
    if (operation.action == "create" and (row is not None or revision)) or (
        operation.action != "create" and revision and (not row or revision != base or (
            not operation.after_operation_id and not same_stamp(operation.base_updated_at, getattr(row, "updated_at", None))
        ))
    ):
        status, error = "conflict", "server_deleted" if row is None else "version_changed"
    elif operation.action != "create" and not row:
        status, error = "invalid", "record_unavailable"
    else:
        try:
            # Existing services may commit internally. Their commits release only an inner savepoint.
            # The outer transaction still atomically owns the business write, feed and receipt.
            with db.begin_nested():
                with Session(bind=db.connection(), join_transaction_mode="create_savepoint", expire_on_commit=False) as business:
                    actor = business.get(User, owner)
                    dispatch(business, actor, operation)
                    business.commit()
                feed.flush_feed(db)
        except HTTPException as exc:
            status = "conflict" if exc.status_code == 409 else "invalid"
            error = "schedule_conflict" if exc.detail == "schedule_conflict" else "business_rule_rejected"
        except (ValidationError, IntegrityError, ValueError, KeyError, TypeError):
            status, error = "invalid", "invalid_record"
        except OperationalError:
            return {"id": str(operation.id), "status": "retryable", "error": "database_busy"}
    db.expire_all()
    current = feed.snapshot(db, user, operation.kind, operation.entity_id)
    receipt = SyncOperation(
        user_id=owner, id=operation.id, device_id=device_id, kind=operation.kind, entity_id=operation.entity_id,
        digest=digest, status=status, revision=int(current["revision"]), error=error,
        request=payload if status == "conflict" else None, server_record=current if status == "conflict" else None,
    )
    db.add(receipt)
    if commit:
        db.commit()
    else:
        db.flush()
    return {**response(receipt), "server": current}


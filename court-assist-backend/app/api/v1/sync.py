"""Private push, pull, receipts and explicit conflict resolution."""

from json import dumps
import logging
from collections import Counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.sync import SyncChange, SyncDevice, SyncOperation, now
from app.models.user import User
from app.schemas.sync import Operation, Pull, Push, Resolution
from app.services import sync_feed as feed, sync_operations as ops


class PrivateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                result = await handler(request)
            except RequestValidationError:
                result = JSONResponse({"detail": "invalid_sync_request"}, status_code=422)
            result.headers["Cache-Control"] = "no-store"
            return result

        return handle


router = APIRouter(prefix="/sync", tags=["offline sync"], route_class=PrivateRoute)
DB = Annotated[Session, Depends(get_db)]
Advocate = Annotated[User, Depends(current_user)]


def touch(db, user, device_id, cursor=None):
    ops.ensure_transaction(db)
    feed.advisory_lock(db, f"courtassist-sync-device:{user.id}:{device_id}")
    row = db.get(SyncDevice, (user.id, device_id))
    if row is None:
        row = SyncDevice(user_id=user.id, id=device_id, cursor=0)
        db.add(row)
    row.last_seen_at = now()
    if cursor is not None:
        row.cursor = max(row.cursor, cursor)
    db.commit()


@router.post("/pull")
def pull(data: Pull, db: DB, user: Advocate):
    cursor = int(data.cursor)
    feed.advisory_lock(db, f"courtassist-sync-feed:{user.id}")
    events = db.scalars(select(SyncChange).where(
        SyncChange.user_id == user.id, SyncChange.revision > cursor,
    ).order_by(SyncChange.revision).limit(data.limit + 1)).all()
    changes, seen = [], set()
    consumed, response_size, next_cursor = 0, 0, cursor
    for event in events[:data.limit]:
        key = (event.kind, event.entity_id)
        if key not in seen:
            change = feed.snapshot(db, user, *key)
            size = len(dumps(change, ensure_ascii=False, separators=(",", ":")).encode())
            if changes and response_size + size > 2 * 1024 * 1024:
                break
            changes.append(change)
            seen.add(key)
            response_size += size
        consumed += 1
        next_cursor = event.revision
    db.commit()
    # The supplied cursor, rather than the returned page, is the device's acknowledged position.
    touch(db, user, data.device_id, cursor)
    return {"changes": changes, "cursor": str(next_cursor), "has_more": len(events) > consumed}


@router.post("/push")
def push(data: Push, db: DB, user: Advocate):
    touch(db, user, data.device_id)
    results = []
    for operation in data.operations:
        try:
            results.append(ops.execute(db, user, data.device_id, operation))
        except OperationalError:
            results.append({"id": str(operation.id), "status": "retryable", "error": "database_busy"})
        finally:
            db.rollback()
    counts = Counter(result['status'] for result in results)
    if any(status != 'applied' for status in counts):
        logging.getLogger(__name__).info('sync_push_results', extra={'outcomes': dict(counts)})
    return {"results": results}


@router.get("/status")
def status(db: DB, user: Advocate, device_id: UUID | None = None):
    latest = db.scalar(select(func.max(SyncChange.revision)).where(SyncChange.user_id == user.id)) or 0
    open_conflicts = db.scalar(select(func.count()).select_from(SyncOperation).where(
        SyncOperation.user_id == user.id, SyncOperation.status == "conflict", SyncOperation.resolved_at.is_(None),
    ))
    device = db.get(SyncDevice, (user.id, device_id)) if device_id else None
    return {"latest_revision": str(latest), "conflicts": open_conflicts,
            "device_cursor": str(device.cursor) if device else None, "last_seen_at": device.last_seen_at if device else None}


@router.get("/records/{kind}/{identifier}")
def record(kind: str, identifier: UUID, db: DB, user: Advocate):
    if kind not in feed.MODELS:
        raise HTTPException(404, "record_not_found")
    feed.advisory_lock(db, f"courtassist-sync-feed:{user.id}")
    change = feed.snapshot(db, user, kind, identifier)
    if change["deleted"]:
        raise HTTPException(404, "record_not_found")
    return change


def receipt(db, user, identifier, lock=False):
    query = select(SyncOperation).where(SyncOperation.user_id == user.id, SyncOperation.id == identifier)
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404, "operation_not_found")
    return row


@router.get("/operations/{identifier}")
def operation(identifier: UUID, db: DB, user: Advocate):
    return ops.result_for(db, user, receipt(db, user, identifier))


@router.get("/conflicts")
def conflicts(db: DB, user: Advocate, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=50)] = 20):
    rows = db.scalars(select(SyncOperation).where(
        SyncOperation.user_id == user.id, SyncOperation.status == "conflict", SyncOperation.resolved_at.is_(None),
    ).order_by(SyncOperation.created_at, SyncOperation.id).offset(offset).limit(limit))
    return {"items": [{**ops.response(row), "local": row.request} for row in rows]}


@router.post("/conflicts/{identifier}/resolve")
def resolve(identifier: UUID, data: Resolution, db: DB, user: Advocate):
    ops.ensure_transaction(db)
    row = receipt(db, user, identifier, lock=True)
    if row.resolved_at:
        if row.resolution["id"] != str(data.id):
            raise HTTPException(409, "conflict_already_resolved")
        return row.resolution
    if row.status != "conflict" or not row.request or data.id == identifier:
        raise HTTPException(422, "invalid_conflict_resolution")
    if row.kind == "appointment":
        feed.advisory_lock(db, f"courtassist-appointments:{user.id}")
    feed.record(db, user.id, row.kind, row.entity_id, lock=True)
    current = feed.snapshot(db, user, row.kind, row.entity_id)
    if current["revision"] != data.server_revision or str(row.revision) != data.server_revision:
        row.revision = int(current["revision"])
        row.server_record = current
        db.commit()
        raise HTTPException(409, "conflict_changed")
    if data.strategy == "server":
        outcome = {"server": current, "revision": current["revision"], "status": "applied"}
    else:
        if row.kind == "payment":
            raise HTTPException(409, "financial_conflict_requires_online_review")
        if data.strategy == "merge" and data.payload is None:
            raise HTTPException(422, "merge_payload_required")
        new = {**row.request, "id": data.id, "base_revision": data.server_revision, "base_updated_at": None,
               "depends_on": [], "after_operation_id": None}
        if data.strategy == "merge":
            new["payload"] = data.payload
        outcome = ops.execute(db, user, data.device_id, Operation.model_validate(new), commit=False)
        if outcome["status"] != "applied":
            raise HTTPException(409, outcome.get("error") or "resolution_rejected")
    row.resolved_at = now()
    row.resolution = {"id": str(data.id), "strategy": data.strategy, "result": outcome}
    db.commit()
    return row.resolution


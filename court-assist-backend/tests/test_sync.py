import os
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")

from app.core.security import create_access_token
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.case import Case
from app.models.diary import CaseDiaryEntry
from app.models.hearing import Hearing
from app.models.phase10 import DraftVersion, Payment
from app.models.sync import SyncChange, SyncOperation
from app.models.user import User

ROOT = "/api/v1"
CASE = {"case_title": "Offline കേസ്", "case_number": "OS 11/2026", "case_category": "Civil", "filing_date": "2026-01-15"}


@pytest.fixture
def scenario():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, hide_parameters=True)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        owner = User(full_name="Advocate One", password_hash="fixture")
        foreign = User(full_name="Advocate Two", password_hash="fixture")
        db.add_all([owner, foreign])
        db.commit()
    def override():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as api:
            yield api, headers(owner.id), headers(foreign.id), engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def headers(owner):
    return {"Authorization": "Bearer " + create_access_token(owner)}


def op(kind, action, payload=None, entity=None, revision="0", **extra):
    return {"id": str(uuid4()), "kind": kind, "entity_id": entity or str(uuid4()),
            "action": action, "payload": payload or {}, "base_revision": revision, **extra}


def push(api, owner, *operations, device=None):
    reply = api.post(ROOT + "/sync/push", headers=owner, json={"device_id": device or str(uuid4()), "operations": operations})
    assert reply.status_code == 200, reply.text
    return reply.json()["results"]


def pull(api, owner, cursor="0", device=None, limit=100):
    reply = api.post(ROOT + "/sync/pull", headers=owner, json={"device_id": device or str(uuid4()), "cursor": cursor, "limit": limit})
    assert reply.status_code == 200, reply.text
    return reply.json()


def record(api, owner, kind, identifier):
    response = api.get(ROOT + f"/sync/records/{kind}/{identifier}", headers=owner)
    assert response.status_code == 200, response.text
    return response.json()


def test_offline_case_diary_task_appointment_dependency_and_replay(scenario):
    api, owner, _, engine = scenario
    device = str(uuid4())
    case = op("case", "create", CASE)
    diary = op("diary", "create", {
        "case_id": case["entity_id"], "entry_date": "2026-01-16", "entry_type": "General Note",
        "title": "Offline diary", "content": "മലയാളം",
    }, depends_on=[case["id"]])
    task = op("task", "create", {"title": "Review order", "case_id": case["entity_id"]}, depends_on=[case["id"]])
    complete = op("task", "complete", entity=task["entity_id"], after_operation_id=task["id"])
    appointment = op("appointment", "create", {
        "title": "Client call", "case_id": case["entity_id"], "appointment_date": "2026-01-20",
        "start_time": "09:00", "end_time": "10:00",
    }, depends_on=[case["id"]])
    assert push(api, owner, diary, device=device)[0]["status"] == "blocked"
    results = push(api, owner, case, diary, task, complete, appointment, device=device)
    assert [result["status"] for result in results] == ["applied"] * 5, results
    assert results[0]["server"]["record"]["id"] == case["entity_id"]
    assert results[3]["server"]["record"]["status"] == "Completed"
    assert push(api, owner, diary, device=device)[0]["revision"] == results[1]["revision"]
    modified = {**diary, "payload": {**diary["payload"], "content": "Different replay"}}
    assert push(api, owner, modified, device=device)[0]["error"] == "operation_id_reused"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CaseDiaryEntry)) == 1
        assert db.scalar(select(func.count()).select_from(Case)) == 1


def test_online_mutations_incremental_tombstone_and_owner_scope(scenario):
    api, owner, other, engine = scenario
    case = api.post(ROOT + "/cases", headers=owner, json=CASE).json()
    identifier = case["id"]
    page = pull(api, owner, limit=1)
    assert page["has_more"] and page["changes"]
    while page["has_more"]:
        next_page = pull(api, owner, page["cursor"], limit=1)
        assert int(next_page["cursor"]) > int(page["cursor"])
        page = next_page
    cursor = page["cursor"]
    assert pull(api, owner, cursor)["changes"] == []
    assert pull(api, other)["changes"] == []
    assert api.get(ROOT + f"/sync/records/case/{identifier}", headers=other).status_code == 404
    diary = api.post(ROOT + "/diary", headers=owner, json={
        "case_id": identifier, "entry_date": "2026-01-18", "entry_type": "General Note", "title": "Delete me",
    }).json()
    before = pull(api, owner, cursor)
    assert any(change["id"] == diary["id"] and not change["deleted"] for change in before["changes"])
    assert api.delete(ROOT + "/diary/" + diary["id"], headers=owner).status_code == 204
    after = pull(api, owner, before["cursor"])
    assert any(change["id"] == diary["id"] and change["deleted"] for change in after["changes"])


def test_stale_case_form_and_competing_diary_deletion(scenario):
    api, owner, _, _ = scenario
    case = api.post(ROOT + "/cases", headers=owner, json=CASE).json()
    case_id = case["id"]
    assert api.patch(ROOT + "/cases/" + case_id, headers=owner, json={"case_title": "New title"}).status_code == 200
    latest = record(api, owner, "case", case_id)
    stale = op("case", "update", {"case_title": "Stale form"}, case_id, latest["revision"], base_updated_at=case["updated_at"])
    stale_result = push(api, owner, stale)[0]
    assert stale_result["status"] == "conflict"
    assert stale_result["server"]["record"]["case_title"] == "New title"
    corrected = op("case", "update", {"case_title": "Reviewed"}, case_id, latest["revision"])
    assert push(api, owner, corrected)[0]["server"]["record"]["case_title"] == "Reviewed"

    diary = api.post(ROOT + "/diary", headers=owner, json={
        "case_id": case_id, "entry_date": "2026-01-20", "entry_type": "General Note", "title": "Notes",
    }).json()
    diary_id = diary["id"]
    before = record(api, owner, "diary", diary_id)
    assert api.patch(ROOT + "/diary/" + diary_id, headers=owner, json={"title": "New notes"}).status_code == 200
    deletion = push(api, owner, op("diary", "delete", entity=diary_id, revision=before["revision"]))[0]
    assert deletion["status"] == "conflict" and deletion["server"]["record"]["title"] == "New notes"
    assert api.delete(ROOT + "/diary/" + diary_id, headers=owner).status_code == 204
    update = push(api, owner, op("diary", "update", {"title": "Offline notes"}, diary_id, deletion["revision"]))[0]
    assert update["status"] == "conflict" and update["server"]["deleted"]


def test_concurrent_diary_and_draft_conflicts_review_and_revalidation(scenario):
    api, owner, other, engine = scenario
    case = api.post(ROOT + "/cases", headers=owner, json=CASE).json()
    draft = api.post(ROOT + "/draft-documents", headers=owner, json={"title": "Draft", "content": "<p>Original</p>"}).json()
    diary = api.post(ROOT + "/diary", headers=owner, json={
        "case_id": case["id"], "entry_date": "2026-01-20", "entry_type": "General Note", "title": "Notes", "content": "Original",
    }).json()
    for kind, row, path in (("draft", draft, "draft-documents"), ("diary", diary, "diary")):
        before = record(api, owner, kind, row["id"])
        assert api.patch(ROOT + f"/{path}/{row['id']}", headers=owner, json={"content": "Device B"}).status_code == 200
        write = op(kind, "update", {"content": "Device A"}, row["id"], before["revision"])
        result = push(api, owner, write)[0]
        assert result["status"] == "conflict" and "Device B" in result["server"]["record"]["content"]
        assert api.get(ROOT + f"/sync/operations/{write['id']}", headers=other).status_code == 404
        resolution_path = ROOT + f"/sync/conflicts/{write['id']}/resolve"
        resolution = {"id": str(uuid4()), "device_id": str(uuid4()), "strategy": "merge",
                      "server_revision": result["revision"], "payload": {"content": "Reviewed Malayalam മലയാളം"}}
        assert api.patch(ROOT + f"/{path}/{row['id']}", headers=owner, json={"content": "Newer server edit"}).status_code == 200
        assert api.post(resolution_path, headers=owner, json=resolution).status_code == 409
        conflict = api.get(ROOT + f"/sync/operations/{write['id']}", headers=owner).json()
        resolution["server_revision"] = conflict["revision"]
        merged = api.post(resolution_path, headers=owner, json=resolution)
        assert merged.status_code == 200, merged.text
        assert api.post(resolution_path, headers=owner, json=resolution).json() == merged.json()
        assert "Reviewed Malayalam" in record(api, owner, kind, row["id"])["record"]["content"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DraftVersion)) >= 4


def test_hearing_history_appointment_conflict_and_case_archive(scenario):
    api, owner, _, engine = scenario
    case = push(api, owner, op("case", "create", CASE))[0]["server"]["record"]
    hearing = push(api, owner, op("hearing", "create", {
        "case_id": case["id"], "hearing_date": "2026-01-22", "hearing_type": "Arguments", "purpose": "Review order",
    }))[0]
    assert hearing["status"] == "applied", hearing
    new_id = str(uuid4())
    moved = push(api, owner, op("hearing", "reschedule", {
        "hearing_date": "2026-02-03", "follow_up_id": new_id, "reason": "New date",
    }, hearing["entity_id"], hearing["revision"]))[0]
    assert moved["status"] == "applied", moved
    assert moved["server"]["record"]["hearing_date"] == "2026-01-22"
    assert record(api, owner, "hearing", new_id)["record"]["hearing_date"] == "2026-02-03"
    appointment = {"title": "Existing", "appointment_date": "2026-01-23", "start_time": "10:00", "end_time": "11:00"}
    assert api.post(ROOT + "/appointments", headers=owner, json=appointment).status_code == 201
    conflict = push(api, owner, op("appointment", "create", {**appointment, "title": "Overlap"}))[0]
    assert conflict["status"] == "conflict" and conflict["error"] == "schedule_conflict"
    latest = record(api, owner, "case", case["id"])
    archived = push(api, owner, op("case", "archive", entity=case["id"], revision=latest["revision"]))[0]
    assert archived["server"]["record"]["is_archived"]


def test_payments_pending_idempotency_and_protected_conflict(scenario):
    api, owner, other, engine = scenario
    client = api.post(ROOT + "/clients", headers=owner, json={
        "full_name": "Client Fixture", "client_type": "individual", "phone_number": "+919876543210",
        "address": "Fixture", "city": "Kochi", "district": "Ernakulam", "state": "Kerala", "postal_code": "682001",
    })
    assert client.status_code == 201, client.text
    data = {"client_id": client.json()["id"], "amount": "100.00", "payment_date": "2026-01-17", "method": "UPI", "status": "received"}
    pending = op("payment", "create", data)
    applied = push(api, owner, pending)[0]
    assert applied["status"] == "applied", applied
    assert applied["server"]["record"]["status"] == "pending"
    assert push(api, owner, pending)[0]["revision"] == applied["revision"]
    assert push(api, other, op("payment", "create", data))[0]["status"] == "invalid"
    assert api.patch(ROOT + "/payments/" + pending["entity_id"], headers=owner, json={"reference": "Newer reference"}).status_code == 200
    conflicted = op("payment", "update", {"reference": "Offline reference"}, pending["entity_id"], applied["revision"])
    result = push(api, owner, conflicted)[0]
    assert result["status"] == "conflict"
    reject = api.post(ROOT + f"/sync/conflicts/{conflicted['id']}/resolve", headers=owner, json={
        "id": str(uuid4()), "device_id": str(uuid4()), "strategy": "local", "server_revision": result["revision"],
    })
    assert reject.status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_interrupted_upload_metadata_and_replay_return_latest_snapshot(scenario):
    api, owner, _, engine = scenario
    create = op("document", "create", {
        "document_name": "Scanned order", "original_filename": "scan.pdf", "mime_type": "application/pdf",
        "file_size": 100, "checksum": "a" * 64, "document_category": "Court Order",
    })
    applied = push(api, owner, create)[0]
    assert applied["status"] == "applied", applied
    assert applied["server"]["record"]["storage_status"] == "upload_pending"
    assert api.patch(ROOT + "/documents/" + create["entity_id"], headers=owner, json={"document_name": "Updated filename"}).status_code == 200
    replay = push(api, owner, create)[0]
    assert replay["revision"] == applied["revision"]
    assert replay["server"]["record"]["document_name"] == "Updated filename"
    assert "storage_key" not in replay["server"]["record"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(SyncOperation).where(SyncOperation.kind == "document")) == 1
        assert db.scalar(select(func.count()).select_from(SyncChange).where(SyncChange.kind == "document")) >= 2


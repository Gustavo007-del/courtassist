"""Release checks that cross service boundaries without replacing business logic."""

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")

from app.core.config import Settings, get_settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.account_erasure import AccountErasure
from app.models.case import Case
from app.models.phase10 import Payment
from app.models.user import User
from app.services.account_erasure import purge
from app.services.malware_scan import Scanner

PREFIX = "/api/v1"
PASSWORD = "FixturePassword123"
CLIENT = {"client_type": "individual", "full_name": "Synthetic client", "phone_number": "+442079460958",
          "address": "Fixture address", "city": "London", "district": "Greater London", "state": "England", "postal_code": "SW1A 1AA"}


@pytest.fixture
def release(tmp_path, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False}, hide_parameters=True)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)

    def database():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, database)
    monkeypatch.setattr(get_settings(), "private_storage_dir", str(tmp_path))
    with TestClient(app) as api:
        yield api, engine, tmp_path
    engine.dispose()


def ok(response):
    assert 200 <= response.status_code < 300, response.text
    return response.json()


def login(api, email):
    return ok(api.post(PREFIX + "/auth/login", json={"identifier": email, "password": PASSWORD}))


def register(api, name):
    email = f"{name}@example.test"
    ok(api.post(PREFIX + "/auth/register", json={"full_name": "Synthetic Advocate " + name,
        "email": email, "password": PASSWORD, "confirm_password": PASSWORD}))
    return login(api, email)


def bearer(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}


def test_http_guards_and_configuration(release):
    api, _, _ = release
    invalid = api.post(PREFIX + "/auth/register", json={"password": "sensitive-fixture-value"})
    assert invalid.status_code == 422 and "sensitive-fixture-value" not in invalid.text
    assert invalid.headers["Cache-Control"] == "no-store"
    assert invalid.headers["X-Content-Type-Options"] == "nosniff"
    assert len(invalid.headers["X-Request-ID"]) == 32
    assert api.get(PREFIX + "/live").status_code == 200
    assert api.get(PREFIX + "/ready").status_code == 200
    assert api.post(PREFIX + "/auth/login", headers={"Content-Length": "999999999"}, content=b"{}").status_code == 413
    assert api.post(PREFIX + "/auth/login", content=iter([b"X" * (9 * 1024 * 1024)])).status_code == 413
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(_env_file=None, app_env="production", database_url="sqlite://", jwt_secret_key="x" * 32)


def test_staging_auth_stops_when_rate_limit_store_is_down(release, monkeypatch):
    from types import SimpleNamespace
    from redis.exceptions import ConnectionError
    from app.api.v1 import rate_limit

    api, _, _ = release
    monkeypatch.setattr(rate_limit, "get_settings", lambda: SimpleNamespace(redis_url="redis://fixture", hardened=True))

    def unavailable(_):
        raise ConnectionError("synthetic Redis outage")

    monkeypatch.setattr(rate_limit, "redis_client", unavailable)
    result = api.post(PREFIX + "/auth/login", json={"identifier": "fixture@example.test", "password": PASSWORD})
    assert result.status_code == 503
    assert "synthetic Redis" not in result.text


def test_session_rotation_reuse_logout_and_remote_revocation(release):
    api, _, _ = release
    first = register(api, "one")
    other_device = login(api, "one@example.test")
    stranger = register(api, "two")
    sessions = ok(api.get(PREFIX + "/auth/sessions/devices", headers=bearer(first)))
    remote = next(row["id"] for row in sessions if not row["current"])
    path = PREFIX + "/auth/sessions/" + remote
    assert api.delete(path, headers=bearer(stranger)).status_code == 404
    assert api.delete(path, headers=bearer(first)).status_code == 204
    assert api.post(PREFIX + "/sync/pull", headers=bearer(other_device), json={"device_id": str(uuid4())}).status_code == 401
    renewed = ok(api.post(PREFIX + "/auth/refresh", json={"refresh_token": first["refresh_token"]}))
    assert api.get(PREFIX + "/users/me", headers=bearer(renewed)).status_code == 200
    assert api.post(PREFIX + "/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert api.get(PREFIX + "/users/me", headers=bearer(renewed)).status_code == 401
    last = login(api, "one@example.test")
    ok(api.post(PREFIX + "/auth/logout", headers=bearer(last), json={"refresh_token": last["refresh_token"]}))
    assert api.get(PREFIX + "/users/me", headers=bearer(last)).status_code == 401


def test_dashboard_query_count_is_independent_of_same_day_hearings(release):
    from zoneinfo import ZoneInfo

    api, engine, _ = release
    headers = bearer(register(api, "dashboard"))

    def overview():
        statements = []

        def count_query(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().startswith("SELECT"):
                statements.append(statement)

        event.listen(engine, "before_cursor_execute", count_query)
        try:
            data = ok(api.get(PREFIX + "/dashboard/overview", headers=headers))
        finally:
            event.remove(engine, "before_cursor_execute", count_query)
        return data, len(statements)

    _, baseline = overview()
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    case = ok(api.post(PREFIX + "/cases", headers=headers, json={"case_title": "Synthetic dashboard case",
        "case_number": "OS 9/2026", "case_category": "Civil", "filing_date": today}))
    for _ in range(3):
        ok(api.post(PREFIX + "/hearings", headers=headers, json={"case_id": case["id"], "hearing_date": today,
            "hearing_type": "Arguments", "purpose": "Synthetic dashboard hearing", "hearing_time": "10:00"}))
    result, with_hearings = overview()
    assert result["summary"]["today_hearings"] == 3
    assert result["hearing_summary"]["potential_conflicts_today"] == 6
    assert with_hearings == baseline


def test_cross_module_advocate_workflow_idor_and_erasure(release):
    api, engine, directory = release
    tokens = register(api, "workflow")
    owner, other = bearer(tokens), bearer(register(api, "unrelated"))
    def post(path, data, extra=None):
        return ok(api.post(PREFIX + path, headers=owner | (extra or {}), json=data))

    ok(api.patch(PREFIX + "/users/me", headers=owner, json={"city": "Fixture City"}))
    client = post("/clients", CLIENT)
    court = post("/courts", {"name": "Synthetic Court", "court_type": "District Court", "state": "Kerala", "district": "Ernakulam", "address": "Fixture address"})
    case = post("/cases", {"case_title": "Synthetic file", "case_number": "OS 1/2026", "case_category": "Civil",
        "filing_date": "2026-01-01", "client_id": client["id"], "court_id": court["id"]})
    case_id = case["id"]
    parties = "/cases/" + case_id + "/parties"
    post(parties, {"party_name": "Synthetic party", "party_role": "Petitioner", "client_id": client["id"]})
    hearing = post("/hearings", {"case_id": case_id, "hearing_date": "2026-01-09", "hearing_type": "Arguments", "purpose": "Synthetic fixture"})
    post("/hearings/" + hearing["id"] + "/complete", {"proceedings_notes": "Synthetic proceedings"})
    diary = post("/diary", {"case_id": case_id, "entry_date": "2026-01-09", "entry_type": "General Note", "title": "Fixture note"})
    task = post("/tasks", {"title": "Review fixture", "case_id": case_id})
    appointment = post("/appointments", {"title": "Fixture appointment", "case_id": case_id,
        "appointment_date": "2026-02-01", "start_time": "09:00", "end_time": "10:00"})
    draft = post("/draft-documents", {"title": "Synthetic draft", "content": "<p>മലയാളം</p>", "case_id": case_id})
    research = post("/research-items", {"title": "Synthetic research note", "item_type": "research_note", "case_id": case_id})
    agreement = post("/fee-agreements", {"client_id": client["id"], "case_id": case_id, "amount": "500.00"})
    payment_input = {"client_id": client["id"], "case_id": case_id, "agreement_id": agreement["id"], "amount": "250.00"}
    key = {"Idempotency-Key": "workflow-payment-fixture"}
    payment = post("/payments", payment_input, key)
    assert post("/payments", payment_input | {"amount": "250"}, key)["id"] == payment["id"]
    assert api.post(PREFIX + "/payments", headers=owner | key, json=payment_input | {"amount": "300.00"}).status_code == 409
    doc = post("/documents", {"document_name": "Synthetic PDF metadata", "original_filename": "test.pdf",
        "mime_type": "application/pdf", "file_size": 100, "case_id": case_id})
    ok(api.patch(PREFIX + "/notification-preferences", headers=owner, json={"draft_reminders": True}))
    notification = post("/notifications/reminders", {"entity_type": "draft", "entity_id": draft["id"], "purpose": "filing",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    for kind, record in [("clients", client), ("courts", court), ("cases", case), ("hearings", hearing),
                          ("diary", diary), ("tasks", task), ("appointments", appointment), ("draft-documents", draft),
                          ("research-items", research), ("fee-agreements", agreement), ("payments", payment),
                          ("documents", doc), ("notifications", notification)]:
        path = f"{PREFIX}/{kind}/{record['id']}"
        assert api.get(path, headers=owner).status_code == 200
        assert api.get(path, headers=other).status_code == 404, path
        assert api.get(path).status_code == 401, path
    assert api.get(PREFIX + parties, headers=other).status_code == 404
    timeline = ok(api.get(PREFIX + "/cases/" + case_id + "/timeline", headers=owner))
    assert timeline["total"] > 0
    assert api.post(PREFIX + "/tasks", headers=other, json={"title": "Cross-owner attempt", "case_id": case_id}).status_code == 404
    cursor = post("/sync/pull", {"device_id": str(uuid4()), "limit": 100})
    assert case_id in {change["id"] for change in cursor["changes"]}
    assert case_id not in {change["id"] for change in ok(api.post(PREFIX + "/sync/pull", headers=other,
        json={"device_id": str(uuid4())}))["changes"]}

    erasure_path = PREFIX + "/users/me/erasure-requests"
    assert api.post(erasure_path, headers=owner, json={"password": "incorrect"}).status_code == 400
    owner_id = UUID(tokens["user"]["id"])
    owner_folder = directory / str(owner_id)
    owner_folder.mkdir()
    (owner_folder / "fixture.jpg").write_bytes(b"synthetic")
    receipt = post("/users/me/erasure-requests", {"password": PASSWORD})
    assert api.get(PREFIX + "/users/me", headers=owner).status_code == 401
    assert api.get(PREFIX + "/users/me", headers=other).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        purge(db, UUID(receipt["id"]))
        purge(db, UUID(receipt["id"]))
        assert db.get(User, owner_id) is None
        assert db.get(Case, UUID(case_id)) is None
        assert db.get(AccountErasure, UUID(receipt["id"])).user_id is None
        assert db.scalar(select(func.count()).select_from(User)) == 1
    assert not owner_folder.exists()


def test_scanner_requires_a_clean_verdict():
    import io
    from fastapi import HTTPException

    class Connection:
        def __init__(self, reply):
            self.reply = reply
        def sendall(self, data):
            assert data == bytes(4)
        def makefile(self, mode):
            return io.BytesIO(self.reply)

    Scanner(Connection(b"stream: OK\x00")).finish()
    with pytest.raises(HTTPException) as infected:
        Scanner(Connection(b"stream: Eicar FOUND\x00")).finish()
    assert infected.value.status_code == 422
    with pytest.raises(HTTPException) as failed:
        Scanner(Connection(b"size limit exceeded\x00")).finish()
    assert failed.value.status_code == 503


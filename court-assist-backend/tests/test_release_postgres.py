"""Concurrency check for a disposable, already-migrated PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="requires disposable PostgreSQL")
def test_concurrent_payment_retries_and_case_edits():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session
    from app.database.session import get_db
    from app.main import app
    from app.models.phase10 import Payment

    engine = create_engine(os.environ["TEST_POSTGRES_URL"], hide_parameters=True)
    prefix = "/api/v1"
    barrier = Barrier(2)
    email = f"{uuid4().hex}@example.test"
    password = "PostgresFixturePassword123"
    key = uuid4().hex

    def database():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as api:
            registration = api.post(prefix + "/auth/register", json={
                "full_name": "Synthetic concurrent fixture", "email": email,
                "password": password, "confirm_password": password,
            })
            assert registration.status_code == 201
            login = api.post(prefix + "/auth/login", json={"identifier": email, "password": password})
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["access_token"], "Idempotency-Key": key}
            client = api.post(prefix + "/clients", headers=headers, json={
                "client_type": "individual", "full_name": "Synthetic client", "phone_number": "+442079460958",
                "address": "Fixture address", "city": "London", "district": "Greater London",
                "state": "England", "postal_code": "SW1A 1AA",
            })
            assert client.status_code == 201

            def submit():
                barrier.wait(timeout=10)
                return api.post(prefix + "/payments", headers=headers, json={"client_id": client.json()["id"], "amount": "42.00"})

            with ThreadPoolExecutor(max_workers=2) as executor:
                pending = [executor.submit(submit) for _ in range(2)]
                results = [job.result(timeout=20) for job in pending]
            assert all(result.status_code == 200 for result in results)
            assert len({result.json()["id"] for result in results}) == 1
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(Payment).where(Payment.idempotency_key == key)) == 1

            case = api.post(prefix + "/cases", headers=headers, json={"case_title": "Synthetic concurrency case",
                "case_number": "OS 2/2026", "case_category": "Civil", "filing_date": "2026-01-01"})
            assert case.status_code == 201
            case_id = case.json()["id"]
            snapshot = api.get(prefix + f"/sync/records/case/{case_id}", headers=headers)
            assert snapshot.status_code == 200
            barrier = Barrier(2)

            def edit(description):
                barrier.wait(timeout=10)
                operation = {"id": str(uuid4()), "kind": "case", "entity_id": case_id, "action": "update",
                    "base_revision": snapshot.json()["revision"], "payload": {"description": description}}
                return api.post(prefix + "/sync/push", headers=headers,
                    json={"device_id": str(uuid4()), "operations": [operation]})

            with ThreadPoolExecutor(max_workers=2) as executor:
                requests = [executor.submit(edit, name) for name in ("Device one", "Device two")]
                updates = [request.result(timeout=20) for request in requests]
            assert all(reply.status_code == 200 for reply in updates)
            assert sorted(reply.json()["results"][0]["status"] for reply in updates) == ["applied", "conflict"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


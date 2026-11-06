import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")

from app.core.config import get_settings
from app.core.security import create_access_token
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.ai import AIChunk, AIJob, utcnow
from app.models.case import Case
from app.models.diary import CaseDiaryEntry
from app.models.document import Document, DocumentOCR, DocumentVersion
from app.models.hearing import Hearing
from app.models.phase10 import DraftDocument, DraftVersion
from app.models.user import User
from app.services import ai_jobs
from app.services.ai_provider import AIError, LlamaCpp, Ollama, Usage, configured_provider, vectors

ROOT = "/api/v1/ai"
MALAYALAM = "2026-11-15 ന് കേസ് പരിഗണിക്കും."
ENGLISH = "The court directs the parties to appear on 2026-11-15."


class FakeProvider:
    name = "fixture"
    model = "fixture-model"
    fingerprint = "f" * 64
    external = False

    def __init__(self, settings):
        self.settings = settings
        self.generate_calls = []
        self.embed_calls = []
        self.responses = []

    def generate(self, messages, schema):
        self.generate_calls.append(json.loads(messages[1]["content"]))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        value = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        return value, Usage(10, 5)

    def embed(self, texts):
        self.embed_calls.append(texts)
        return [[1.0, 0.0] if "target" in text or len(texts) == 1 else [0.0, 1.0] for text in texts], Usage(2)


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool, hide_parameters=True)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    settings = get_settings()
    for key, value in {
        "redis_url": "redis://localhost:6379/15", "ai_requests_per_minute": 20,
        "ai_embedding_model": "fixture-embedding", "ai_enabled": True,
    }.items():
        monkeypatch.setattr(settings, key, value)
    fake = FakeProvider(settings)
    from app.api.v1 import ai as api_module
    monkeypatch.setattr(ai_jobs, "configured_provider", lambda: fake)
    monkeypatch.setattr(api_module, "configured_provider", lambda: fake)
    monkeypatch.setattr(ai_jobs, "SessionLocal", sessions)

    def case(user, title):
        return Case(user_id=user.id, case_title=title, case_number="Fixture 23/2026",
                    case_category="Civil", filing_date=date(2026, 10, 2), current_status="Pending",
                    description="Selected case information.", priority="Medium")

    def doc(db, user, case, title, pages):
        row = Document(user_id=user.id, case_id=case.id, document_name=title, original_filename="order.pdf",
                       file_extension=".pdf", mime_type="application/pdf", file_size=1000, document_category="Order",
                       storage_status="cloud_stored", current_version_id=uuid4())
        db.add(row)
        db.flush()
        db.add(DocumentVersion(id=row.current_version_id, document_id=row.id, user_id=user.id, version_number=1,
                               storage_key="test-" + str(row.id), original_filename="order.pdf",
                               file_size=1000, storage_status="cloud_stored"))
        db.flush()
        db.add(DocumentOCR(document_id=row.id, user_id=user.id, document_version_id=row.current_version_id,
                           processing_status="completed", processed_at=utcnow(), page_results=pages))
        return row

    with sessions() as db:
        one = User(full_name="Test advocate", password_hash="fixture")
        two = User(full_name="Another advocate", password_hash="fixture")
        db.add_all([one, two])
        db.flush()
        first, other = case(one, "Case fixture"), case(two, "Other case")
        db.add_all([first, other])
        db.flush()
        document = doc(db, one, first, "Selected order", [
            {"page_number": 1, "extracted_text": "A background paragraph."},
            {"page_number": 2, "extracted_text": f"target. {ENGLISH} {MALAYALAM}"},
            {"page_number": 3, "extracted_text": ""},
        ])
        hidden = doc(db, one, first, "Unselected order", [{"page_number": 1, "extracted_text": "unselected confidential fixture"}])
        foreign = doc(db, two, other, "Other owner's order", [{"page_number": 1, "extracted_text": "other owner confidential fixture"}])
        hearing = Hearing(user_id=one.id, case_id=first.id, hearing_date=date(2026, 11, 15), hearing_type="Arguments",
                          purpose="Consider the application", status="Scheduled")
        diary = CaseDiaryEntry(user_id=one.id, case_id=first.id, entry_date=date(2026, 11, 16),
                               title="Private notes", content=MALAYALAM, entry_type="General Note")
        draft = DraftDocument(user_id=one.id, case_id=first.id, title="Draft", content="<p>Original sentence.</p>")
        db.add_all([hearing, diary, draft])
        db.commit()

    def override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    headers = [{"Authorization": "Bearer " + create_access_token(user.id)} for user in (one, two)]
    try:
        with TestClient(app) as api:
            yield api, headers, sessions, fake, one, two, first, document, hidden, foreign, hearing, diary, draft
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def enable(api, headers, **extra):
    response = api.patch(ROOT + "/preferences", headers=headers, json={
        "enabled": True, "documents": True, "assistant": True, **extra,
    })
    assert response.status_code == 200, response.text


def evidence(source, quote, section, **extra):
    return {"source": source, "quote": quote, "section": section, **extra}


def run(sessions, identifier):
    with sessions() as db:
        assert ai_jobs.claim(db) == UUID(identifier)
    ai_jobs.process(UUID(identifier))


def submit(api, headers, endpoint, payload=None):
    response = api.post(ROOT + endpoint, headers=headers, json=payload or {})
    assert response.status_code == 202, response.text
    return response.json()


def result(api, headers, job):
    response = api.get(ROOT + "/jobs/" + job["id"], headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_default_consent_external_fingerprint_and_revocation(setup):
    api, (one, two), sessions, fake, _, _, case, doc, *_ = setup
    prefs = api.get(ROOT + "/preferences", headers=one)
    assert prefs.status_code == 200 and prefs.headers["cache-control"] == "no-store"
    assert not any(prefs.json()[key] for key in ("enabled", "assistant", "documents", "external"))
    assert api.post(ROOT + f"/documents/{doc.id}/summarize", json={}, headers=one).status_code == 403
    assert api.patch(ROOT + "/preferences", headers=one, json={"enabled": True}).status_code == 200
    assert api.post(ROOT + f"/documents/{doc.id}/summarize", json={}, headers=one).json()["detail"] == "document_consent_required"
    assert api.post(ROOT + "/ask", headers=one, json={
        "question": "Status?", "sources": [{"kind": "case", "id": str(case.id)}],
    }).json()["detail"] == "assistant_consent_required"
    fake.external = True
    enable(api, one)
    assert api.patch(ROOT + "/preferences", headers=one, json={"external": True}).status_code == 422
    enable(api, one, external=True, external_confirmation=fake.fingerprint)
    assert api.post(ROOT + f"/documents/{doc.id}/summarize", headers=one, json={}).json()["detail"] == "external_consent_required"
    job = submit(api, one, f"/documents/{doc.id}/summarize", {"external_confirmation": fake.fingerprint})
    with sessions() as db:
        assert ai_jobs.claim(db) == UUID(job["id"])
    assert api.patch(ROOT + "/preferences", headers=one, json={"enabled": False}).status_code == 200
    ai_jobs.process(UUID(job["id"]))
    assert result(api, one, job)["status"] == "cancelled" and not fake.generate_calls
    assert api.get(ROOT + "/jobs/" + job["id"], headers=two).status_code == 404


def test_malayalam_summary_citations_and_untrusted_quotes(setup):
    api, (headers, _), sessions, fake, _, _, _, doc, *_ = setup
    enable(api, headers)
    fake.responses.append({"items": [
        evidence(2, MALAYALAM, "directions"),
        evidence(2, "Invented citation XYZ v ABC", "provisions"),
        evidence(999, ENGLISH, "decision"),
    ]})
    job = submit(api, headers, f"/documents/{doc.id}/summarize", {"language": "ml"})
    run(sessions, job["id"])
    row = result(api, headers, job)
    assert row["status"] == "completed", row
    item, = row["result"]["items"]
    assert item["quote"] == MALAYALAM and item["source"]["page"] == 2
    assert item["source"]["version"] == str(doc.current_version_id)
    assert "provisions" in row["result"]["missing_sections"]
    assert set(row["result"]["warnings"]) == {"partial_ocr", "unsupported_evidence"}
    assert row["input_tokens"] == 10 and row["output_tokens"] == 5
    assert api.get(ROOT + f"/documents/{doc.id}/results", headers=headers).json()["total"] == 1
    with sessions() as db:
        assert db.get(Document, doc.id).current_version_id == doc.current_version_id


def test_date_extraction_and_explicit_diary_approval(setup):
    api, (headers, _), sessions, fake, _, _, case, doc, *_ = setup
    enable(api, headers)
    fake.responses.append({"items": [
        evidence(1, ENGLISH, "hearing", date="2026-11-15", date_status="explicit"),
        evidence(1, MALAYALAM, "limitation_mentioned", date="2026-12-15", date_status="explicit"),
    ]})
    job = submit(api, headers, f"/documents/{doc.id}/extract-dates", {"first_page": 2, "last_page": 2})
    run(sessions, job["id"])
    row = result(api, headers, job)
    assert row["result"]["items"][0]["date"] == "2026-11-15"
    assert row["result"]["items"][1]["date"] is None
    assert row["result"]["items"][1]["date_status"] == "inferred"
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(CaseDiaryEntry)) == 1
        assert db.scalar(select(func.count()).select_from(Hearing)) == 1
    payload = {"item_index": 0, "case_id": str(case.id), "title": "Reviewed event", "text": ENGLISH, "entry_date": "2026-11-15"}
    endpoint = ROOT + "/jobs/" + job["id"] + "/approve-diary"
    first = api.post(endpoint, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert api.post(endpoint, headers=headers, json=payload).json() == first.json()
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(CaseDiaryEntry)) == 2
        assert db.scalar(select(func.count()).select_from(Hearing)) == 1


def test_rag_context_and_vector_isolation_conversations_and_deletion(setup):
    api, (one, two), sessions, fake, owner, _, case, doc, hidden, foreign, *_ = setup
    enable(api, one)
    enable(api, two)
    question = {"case_id": str(case.id), "question": "Find the target direction.",
                "sources": [{"kind": "document", "id": str(doc.id)}]}
    rejected = {**question, "sources": [{"kind": "document", "id": str(foreign.id)}]}
    assert api.post(ROOT + "/ask", headers=one, json=rejected).status_code == 404
    assert api.post(ROOT + "/ask", headers=two, json=question).status_code == 404
    fake.responses.append({"items": [evidence(1, ENGLISH, "answer")]})
    job = submit(api, one, "/ask", question)
    run(sessions, job["id"])
    row = result(api, one, job)
    assert row["status"] == "completed", row
    assert row["result"]["items"][0]["source"]["page"] == 2
    assert row["input_tokens"] == 14
    assert all("confidential fixture" not in str(payload) for payload in fake.generate_calls + fake.embed_calls)
    with sessions() as db:
        chunks = db.scalars(select(AIChunk)).all()
        assert len(chunks) == 2 and {chunk.document_id for chunk in chunks} == {doc.id}
        assert {chunk.user_id for chunk in chunks} == {owner.id}
    conversation = "/conversations/" + row["conversation_id"]
    assert api.get(ROOT + conversation, headers=two).status_code == 404
    assert api.get(ROOT + "/conversations", headers=one).json()["items"][0]["id"] == row["conversation_id"]
    fake.responses.append({"items": []})
    followup = submit(api, one, conversation + "/messages", {
        **question, "question": "Is there another direction?", "previous_job_id": job["id"],
    })
    run(sessions, followup["id"])
    assert result(api, one, followup)["result"]["insufficient"]
    assert fake.generate_calls[-1]["previous_question"] == question["question"]
    assert api.delete(ROOT + conversation, headers=one).status_code == 204
    assert api.get(ROOT + "/jobs/" + job["id"], headers=one).status_code == 404
    with sessions() as db:
        assert not db.scalars(select(AIChunk)).all()
        erased = db.get(AIJob, UUID(job["id"]))
        assert erased.request_data is None and erased.result is None and erased.conversation_id is None
    assert api.get(ROOT + "/usage/summary", headers=one).json()["requests"] == 2


def test_chronology_review_and_export(setup):
    api, (headers, _), sessions, fake, _, _, case, _, _, _, hearing, diary, _ = setup
    enable(api, headers)
    fake.responses.append({"items": [
        evidence(1, "hearing_date: 2026-11-15", "hearing", date="2026-11-15", date_status="explicit"),
        evidence(2, "entry_date: 2026-11-16", "hearing", date="2026-11-16", date_status="explicit"),
    ]})
    job = submit(api, headers, f"/cases/{case.id}/chronology", {"sources": [
        {"kind": "hearing", "id": str(hearing.id)}, {"kind": "diary", "id": str(diary.id)},
    ]})
    run(sessions, job["id"])
    result_url = ROOT + f"/cases/{case.id}/chronology/{job['id']}"
    row = api.get(result_url, headers=headers).json()
    assert [item["date"] for item in row["result"]["items"]] == ["2026-11-15", "2026-11-16"]
    assert all(item["check_other_dates"] for item in row["result"]["items"])
    export_url = ROOT + "/jobs/" + job["id"] + "/export"
    assert api.get(export_url, headers=headers).status_code == 409
    assert api.patch(ROOT + "/jobs/" + job["id"] + "/review", headers=headers, json={"text": MALAYALAM}).status_code == 200
    exported = api.get(export_url, headers=headers)
    assert exported.text == MALAYALAM and exported.headers["cache-control"] == "no-store"


def test_draft_and_diary_suggestions_require_approval(setup):
    api, (headers, _), sessions, fake, _, _, case, _, _, _, _, diary, draft = setup
    enable(api, headers)
    fake.responses.extend([{"suggestion": MALAYALAM}, {"suggestion": "Revised private note."}])
    job = submit(api, headers, f"/drafts/{draft.id}/rewrite", {"text": "Original sentence.", "language": "ml"})
    run(sessions, job["id"])
    row = result(api, headers, job)
    assert row["result"]["suggestion"] == MALAYALAM
    with sessions() as db:
        assert db.get(DraftDocument, draft.id).content == draft.content
    response = api.post(ROOT + "/jobs/" + job["id"] + "/approve-draft", headers=headers, json={
        "expected_updated_at": row["draft_revision"], "text": MALAYALAM + "<script>alert(1)</script>", "mode": "replace",
    })
    assert response.status_code == 200, response.text
    with sessions() as db:
        current = db.get(DraftDocument, draft.id).content
        assert MALAYALAM in current and "<script>" not in current and "&lt;script&gt;" in current
        assert db.scalar(select(DraftVersion).where(DraftVersion.document_id == draft.id)).content == draft.content
    note = submit(api, headers, "/diary/organize", {"entry_id": str(diary.id), "text": diary.content, "action": "organize"})
    run(sessions, note["id"])
    response = api.post(ROOT + "/jobs/" + note["id"] + "/approve-diary", headers=headers, json={
        "case_id": str(case.id), "entry_date": "2026-11-17", "title": "Reviewed note", "text": "Revised private note.",
    })
    assert response.status_code == 200, response.text
    with sessions() as db:
        assert db.get(CaseDiaryEntry, diary.id).content == MALAYALAM
        assert db.get(CaseDiaryEntry, UUID(response.json()["diary_entry_id"])).content == "Revised private note."


def test_retries_invalid_output_stale_worker_and_idempotency(setup):
    api, (headers, _), sessions, fake, _, _, _, doc, *_ = setup
    enable(api, headers)
    payload = {"request_id": str(uuid4())}
    path = f"/documents/{doc.id}/summarize"
    job = submit(api, headers, path, payload)
    assert submit(api, headers, path, payload)["id"] == job["id"]
    fake.responses.extend([AIError("provider_busy", True), "malformed response with confidential fixture"])
    run(sessions, job["id"])
    assert result(api, headers, job)["status"] == "pending"
    with sessions() as db:
        assert ai_jobs.claim(db) is None
        row = db.get(AIJob, UUID(job["id"]))
        row.available_at = utcnow() - timedelta(seconds=1)
        db.commit()
    run(sessions, job["id"])
    failed = result(api, headers, job)
    assert failed["status"] == "failed" and failed["attempts"] == 2 and failed["error_code"] == "invalid_provider_response"
    assert "confidential fixture" not in json.dumps(failed)
    retry = submit(api, headers, "/jobs/" + job["id"] + "/retry")
    with sessions() as db:
        assert ai_jobs.claim(db) == UUID(retry["id"])
        row = db.get(AIJob, UUID(retry["id"]))
        row.lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
        ai_jobs.sweep(db)
    assert result(api, headers, retry)["error_code"] == "worker_interrupted"


def test_rate_limits_and_retention_erase_content_only(setup, monkeypatch):
    api, (headers, _), sessions, fake, _, _, _, doc, *_ = setup
    enable(api, headers, retention_days=1)
    monkeypatch.setattr(fake.settings, "ai_requests_per_minute", 1)
    job = submit(api, headers, f"/documents/{doc.id}/extract-metadata")
    with sessions() as db:
        row = db.get(AIJob, UUID(job["id"]))
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        ai_jobs.sweep(db)
        assert row.request_data is None and row.document_id is None
    assert api.get(ROOT + "/jobs/" + job["id"], headers=headers).status_code == 404
    assert api.post(ROOT + f"/documents/{doc.id}/summarize", headers=headers, json={}).status_code == 429
    assert api.get(ROOT + "/usage/summary", headers=headers).json()["requests"] == 1
    invalid = api.post(ROOT + "/ask", headers=headers, json={"question": "Confidential invalid fixture", "sources": []})
    assert invalid.status_code == 422 and "Confidential invalid fixture" not in invalid.text


def test_provider_configuration_and_response_shape(monkeypatch):
    settings = get_settings()
    for name, value in {"ai_enabled": False, "ai_provider": "ollama", "ai_base_url": "http://127.0.0.1:11434",
                        "ai_model": "local-fixture", "ai_external": False}.items():
        monkeypatch.setattr(settings, name, value)
    assert configured_provider() is None
    settings.ai_enabled = True
    provider = configured_provider()
    assert isinstance(provider, Ollama)
    monkeypatch.setattr(provider, "post", lambda *args: {
        "done": True, "message": {"content": "{}"}, "prompt_eval_count": 5, "eval_count": 2,
    })
    assert provider.generate([], {}) == ("{}", Usage(5, 2))
    settings.ai_external = True
    assert configured_provider() is None
    monkeypatch.setattr(settings, "ai_base_url", "https://verified-provider.example.invalid")
    monkeypatch.setattr(settings, "ai_provider_policy", "Fixture retention policy")
    assert configured_provider() is None
    monkeypatch.setattr(settings, "ai_external_no_training_verified", True)
    assert configured_provider().external
    settings.ai_external = False
    settings.ai_provider = "llama_cpp"
    provider = configured_provider()
    assert isinstance(provider, LlamaCpp)
    monkeypatch.setattr(provider, "post", lambda *args: {
        "data": [{"index": 1, "embedding": [0, 3]}, {"index": 0, "embedding": [2, 0]}],
        "usage": {"prompt_tokens": 6},
    })
    assert provider.embed(["one", "two"]) == ([[1.0, 0.0], [0.0, 1.0]], Usage(6))
    with pytest.raises(AIError):
        vectors([[float("nan"), 1]], 1)


def test_named_english_and_malayalam_dates_require_explicit_year():
    from app.services.ai_generation import explicit_dates
    assert explicit_dates("Order on 19 November 2024. 2024 നവംബർ 19") == {date(2024, 11, 19)}
    assert explicit_dates("within 90 days or 19 November") == set()


def test_actual_malayalam_gazette_pdf_when_supplied(setup):
    path = os.environ.get("COURT_ASSIST_MALAYALAM_TEST_PDF")
    if not path:
        pytest.skip("Set COURT_ASSIST_MALAYALAM_TEST_PDF to the public Gazette fixture")
    from app.services.document_ocr import extract_pages
    from app.services.ai_context import split_passages
    api, (headers, _), sessions, fake, _, _, _, doc, *_ = setup
    pages = extract_pages(Path(path).read_bytes(), "application/pdf", "pypdf")
    sample = next(page for page in pages if re.search(r"[\u0d00-\u0d7f]{3}", page["extracted_text"]))
    passage = next(part for part in split_passages(sample["extracted_text"]) if re.search(r"[\u0d00-\u0d7f]{3}", part))
    quote = next(line.strip() for line in passage.splitlines() if re.search(r"[\u0d00-\u0d7f]{3}", line) and 8 <= len(line.strip()) <= 400)
    number = list(split_passages(sample["extracted_text"])).index(passage) + 1
    assert number <= 7, "Test Gazette excerpt should be in the first processing batch"
    with sessions() as db:
        ocr = db.scalar(select(DocumentOCR).where(DocumentOCR.document_id == doc.id))
        ocr.page_results = [sample]
        db.commit()
    enable(api, headers)
    fake.responses.append({"items": [evidence(number, quote, "background")]})
    fake.responses.extend({"items": []} for _ in range((len(list(split_passages(sample["extracted_text"]))) - 1) // 7))
    job = submit(api, headers, f"/documents/{doc.id}/summarize")
    run(sessions, job["id"])
    row = result(api, headers, job)
    assert row["status"] == "completed", row
    assert row["result"]["items"][0]["quote"] == " ".join(quote.split())
    assert row["result"]["items"][0]["source"]["page"] == sample["page_number"]


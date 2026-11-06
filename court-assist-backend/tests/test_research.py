import io
import os
import uuid
from datetime import date
import pytest
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")
from app import models
from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.api.v1.dependencies import current_user
from app.models.user import User
from app.models.case import Case
from app.models.document import Document, DocumentVersion, DocumentOCR
from app.models.phase10 import ResearchItem
from app.services.document_ocr import extract_pages


@pytest.fixture
def research_api():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine, "connect", lambda dbapi, record: dbapi.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        one = User(
            id=uuid.uuid4(), full_name="Research Advocate", password_hash="unused"
        )
        two = User(id=uuid.uuid4(), full_name="Other Advocate", password_hash="unused")
        db.add_all([one, two])
        db.flush()
        case = Case(
            user_id=one.id,
            case_title="Fixture case",
            case_number="Fixture 1",
            case_category="Civil",
            filing_date=date(2026, 1, 1),
            current_status="Pending",
            description="",
            priority="Medium",
        )
        other_case = Case(
            user_id=two.id,
            case_title="Other private case",
            case_number="Other 2",
            case_category="Civil",
            filing_date=date(2026, 1, 1),
            current_status="Pending",
            description="",
            priority="Medium",
        )
        documents = []
        for owner in (one, two):
            doc = Document(
                id=uuid.uuid4(),
                user_id=owner.id,
                document_name="Fixture source",
                original_filename="fixture.pdf",
                file_extension=".pdf",
                mime_type="application/pdf",
                file_size=100,
                document_category="Judgment",
                storage_status="cloud_stored",
                current_version_id=uuid.uuid4(),
            )
            db.add(doc)
            db.flush()
            db.add(
                DocumentVersion(
                    id=doc.current_version_id,
                    document_id=doc.id,
                    user_id=owner.id,
                    version_number=1,
                    storage_key="private/" + str(owner.id),
                    original_filename="fixture.pdf",
                    file_size=100,
                    storage_status="cloud_stored",
                )
            )
            documents.append(doc)
        db.add_all([case, other_case])
        db.flush()
        source = "Case title: Fixture source case\nDistrict Court of Fixture\nOS 12/2026\nCitation: FIXTURE-REFERENCE\nOrder Date: 03/11/2026\nPetitioner: Fixture Person\nPrivate OCR phrase"
        db.add(
            DocumentOCR(
                user_id=one.id,
                document_id=documents[0].id,
                document_version_id=documents[0].current_version_id,
                processing_status="completed",
                extracted_text=source,
                page_results=[{"page_number": 7, "extracted_text": source}],
            )
        )
        db.commit()

    def session_override():
        with Session(engine) as db:
            yield db

    active = [one]
    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[current_user] = lambda: active[0]
    try:
        with TestClient(app) as api:
            yield api, active, one, two, case, other_case, documents, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_research_search_tags_notes_case_links_and_ownership(research_api):
    api, active, one, two, case, other_case, docs, engine = research_api
    prefix = "/api/v1"
    for bad_link in ({"case_id": str(other_case.id)}, {"document_id": str(docs[1].id)}):
        assert (
            api.post(
                prefix + "/research-items", json={"title": "Forbidden link", **bad_link}
            ).status_code
            == 404
        )
    created = api.post(
        prefix + "/research-items",
        json={
            "title": "Private reference",
            "citation": "  EXACT user citation  ",
            "full_text": "Unique fulltext word",
            "notes": "Personal analysis keyword",
            "case_id": str(case.id),
            "document_id": str(docs[0].id),
            "tags": ["Civil", "civil"],
            "language": "ml",
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    identifier = item["id"]
    assert item["citation"] == "  EXACT user citation  " and item["tags"] == ["Civil"]
    assert (
        api.patch(
            prefix + "/research-items/" + identifier,
            json={"citation": "  Amended exact citation  "},
        ).json()["citation"]
        == "  Amended exact citation  "
    )
    for term in ("fulltext", "analysis", "Private OCR phrase", "Civil"):
        assert (
            api.get(prefix + "/research-items/search", params={"q": term}).json()[
                "total"
            ]
            == 1
        )
    assert (
        api.get(prefix + "/research-items", params={"language": "en"}).json()["total"]
        == 0
    )
    assert (
        api.get(prefix + f"/cases/{case.id}/research-items").json()["items"][0]["id"]
        == identifier
    )
    assert (
        api.post(prefix + f"/research-items/{identifier}/favorite").json()["favorite"]
        is True
    )
    assert (
        api.get(prefix + "/research-items", params={"favorite": "true"}).json()["total"]
        == 1
    )
    note = api.post(
        prefix + "/research-notes",
        json={
            "title": "Private analysis",
            "content": "<p>My analysis</p>",
            "quoted_text": "  Exact quotation  ",
            "references": "User supplied page 7",
            "item_id": identifier,
            "case_id": str(case.id),
            "tags": ["Civil"],
            "pinned": True,
        },
    )
    assert note.status_code == 201, note.text
    note_id = note.json()["id"]
    assert note.json()["quoted_text"] == "  Exact quotation  "
    tag = api.get(prefix + "/research-tags").json()[0]
    assert api.delete(prefix + "/research-tags/" + tag["id"]).status_code == 409
    assert (
        api.patch(
            prefix + "/research-tags/" + tag["id"], json={"name": "Civil procedure"}
        ).status_code
        == 200
    )
    assert api.get(prefix + "/research-items/" + identifier).json()["tags"] == [
        "Civil procedure"
    ]
    assert api.get(prefix + "/research-notes/" + note_id).json()["tags"] == [
        "Civil procedure"
    ]
    assert (
        api.get(
            prefix + "/research-notes",
            params={"q": "analysis", "tag": "Civil procedure", "pinned": "true"},
        ).json()["total"]
        == 1
    )
    assert api.post(prefix + f"/research-items/{identifier}/archive").status_code == 200
    assert api.get(prefix + "/research-items").json()["total"] == 0
    assert (
        api.get(prefix + "/research-items", params={"archived": "true"}).json()["total"]
        == 1
    )
    assert api.post(prefix + f"/research-items/{identifier}/restore").status_code == 200
    assert api.delete(prefix + "/research-notes/" + note_id).status_code == 200
    assert api.get(prefix + "/research-notes").json()["total"] == 0
    assert api.post(prefix + f"/research-notes/{note_id}/restore").status_code == 200
    active[0] = two
    assert api.get(prefix + "/research-items").json()["total"] == 0
    for path in (
        f"/research-items/{identifier}",
        f"/research-items/{identifier}/extraction-status",
        f"/research-notes/{note_id}",
        f"/cases/{case.id}/research-items",
    ):
        assert api.get(prefix + path).status_code == 404
    assert (
        api.patch(
            prefix + "/research-tags/" + tag["id"], json={"name": "Intrusion"}
        ).status_code
        == 404
    )
    assert (
        api.post(
            prefix + "/research-notes",
            json={"title": "Intrusion", "item_id": identifier},
        ).status_code
        == 404
    )
    assert (
        api.post(
            prefix + f"/cases/{other_case.id}/research-items",
            json={"item_id": identifier},
        ).status_code
        == 404
    )
    own = api.post(
        prefix + "/research-items", json={"title": "Other user source"}
    ).json()
    active[0] = one
    assert (
        api.post(
            prefix + f"/cases/{case.id}/research-items", json={"item_id": own["id"]}
        ).status_code
        == 404
    )
    assert (
        api.post(
            prefix + "/research-items",
            json={"title": "Bad URL", "source_url": "javascript:alert(1)"},
        ).status_code
        == 422
    )
    assert (
        api.post(
            prefix + "/research-items",
            json={
                "title": "False verification",
                "verification_status": "verified_external",
            },
        ).status_code
        == 422
    )


def test_csv_preview_confirmation_is_private_validated_and_idempotent(research_api):
    api, active, one, two, *_ = research_api
    url = "/api/v1/research-items/import"
    bad = api.post(
        url,
        json={
            "csv_text": "title,source_url\nGood,https://example.invalid/a\nBad,javascript:bad\n"
        },
    ).json()
    assert len(bad["errors"]) == 1
    assert (
        api.post(url, json={"batch_id": bad["batch_id"], "confirm": True}).status_code
        == 422
    )
    assert api.get("/api/v1/research-items").json()["total"] == 0
    text = 'title,citation,tags\nImported note," User, supplied citation ",Evidence\nAnother note," User, supplied citation ",Evidence\n'
    preview = api.post(url, json={"csv_text": text}).json()
    assert not preview["errors"] and preview["rows"][1]["duplicate"]
    active[0] = two
    assert (
        api.post(
            url,
            json={
                "batch_id": preview["batch_id"],
                "confirm": True,
                "allow_duplicates": True,
            },
        ).status_code
        == 404
    )
    active[0] = one
    assert (
        api.post(
            url, json={"batch_id": preview["batch_id"], "confirm": True}
        ).status_code
        == 409
    )
    imported = api.post(
        url,
        json={
            "batch_id": preview["batch_id"],
            "confirm": True,
            "allow_duplicates": True,
        },
    )
    assert imported.status_code == 200, imported.text
    assert len(imported.json()["imported_ids"]) == 2
    assert (
        api.post(url, json={"batch_id": preview["batch_id"], "confirm": True}).json()[
            "imported_ids"
        ]
        == imported.json()["imported_ids"]
    )
    page = api.get("/api/v1/research-items", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    record = api.get("/api/v1/research-items/" + page["items"][0]["id"]).json()
    assert (
        record["citation"] == " User, supplied citation "
        and record["source_status"] == "imported"
    )


def test_metadata_is_suggested_only_and_requires_current_owned_source(research_api):
    api, active, one, two, case, other_case, docs, engine = research_api
    created = api.post(
        "/api/v1/research-items",
        json={
            "title": "Metadata fixture",
            "citation": "Preserve until reviewed",
            "document_id": str(docs[0].id),
            "case_id": str(case.id),
        },
    ).json()
    identifier = created["id"]
    url = "/api/v1/research-items/" + identifier
    result = api.post(url + "/extract-metadata")
    assert result.status_code == 200, result.text
    extraction = result.json()
    proposal = next(
        row for row in extraction["suggestions"] if row["field"] == "citation"
    )
    assert proposal["page_number"] == 7 and proposal["source_text"]
    assert api.get(url).json()["citation"] == "Preserve until reviewed"
    request = {
        "metadata_id": extraction["metadata_id"],
        "choices": [
            {
                "field": "citation",
                "source_value": proposal["value"],
                "value": proposal["value"],
                "status": "accepted",
            }
        ],
    }
    invalid = {
        "metadata_id": extraction["metadata_id"],
        "choices": [
            {
                "field": "citation",
                "source_value": "Fabricated source",
                "value": "Anything",
                "status": "accepted",
            }
        ],
    }
    assert api.post(url + "/confirm-metadata", json=invalid).status_code == 422
    active[0] = two
    assert api.post(url + "/confirm-metadata", json=request).status_code == 404
    active[0] = one
    accepted = api.post(url + "/confirm-metadata", json=request)
    assert accepted.status_code == 200, accepted.text
    assert (
        accepted.json()["citation"] == proposal["value"]
        and accepted.json()["verification_status"] == "unverified"
    )
    assert accepted.json()["source_status"] == "document_extracted"
    assert api.get(url + "/audit").json()
    with Session(engine) as db:
        assert db.get(Case, case.id).case_title == "Fixture case"
        assert (
            db.get(Document, docs[0].id).current_version_id
            == docs[0].current_version_id
        )
    assert "confidence" in proposal and proposal["confidence"] is None
    with Session(engine) as db:
        doc = db.get(Document, docs[0].id)
        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc.id,
            user_id=one.id,
            version_number=2,
            storage_key="private/new-version",
            original_filename="replacement.pdf",
            file_size=100,
            storage_status="cloud_stored",
        )
        db.add(version)
        db.flush()
        doc.current_version_id = version.id
        db.commit()
    assert api.post(url + "/confirm-metadata", json=request).status_code == 409


def test_utf8_and_docx_extraction_preserves_text_without_invented_page_numbers():
    text = "Case title: Source fixture\nമലയാളം ഗവേഷണ കുറിപ്പ്"
    pages = extract_pages(text.encode("utf-8"), "text/plain", "pypdf")
    assert pages[0]["extracted_text"] == text and pages[0]["page_number"] is None
    from docx import Document as WordDocument

    document = WordDocument()
    document.add_paragraph("Citation: SOURCE-FIXTURE")
    document.add_paragraph("മലയാളം")
    content = io.BytesIO()
    document.save(content)
    result = extract_pages(
        content.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pypdf",
    )
    assert result[0]["extracted_text"] == "Citation: SOURCE-FIXTURE\nമലയാളം"
    assert result[0]["page_number"] is None


def test_research_uses_existing_async_document_worker(research_api, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.api.v1 import documents as documents_api
    from app.services import document_ocr
    from app.services.draft_generation import pdf

    api, active, one, two, case, other_case, docs, engine = research_api
    active[0] = two
    sent = []
    monkeypatch.setattr(
        documents_api, "queue_ocr", lambda identifier: sent.append(identifier)
    )
    item = api.post(
        "/api/v1/research-items",
        json={"title": "Async fixture", "document_id": str(docs[1].id)},
    ).json()
    response = api.post("/api/v1/research-items/" + item["id"] + "/extract-metadata")
    assert response.status_code == 200, response.text
    assert response.json()["processing_status"] == "pending" and len(sent) == 1
    payload = pdf(
        "<p>Citation: ASYNC-FIXTURE</p><p>Source text supplied by advocate</p>"
    )

    class FakeS3:
        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(payload)}

    monkeypatch.setattr(document_ocr, "client", lambda: FakeS3())
    monkeypatch.setattr(document_ocr, "SessionLocal", sessionmaker(bind=engine))
    document_ocr.process_ocr(sent[0])
    status = api.get(
        "/api/v1/research-items/" + item["id"] + "/extraction-status"
    ).json()
    assert status["processing_status"] == "completed"
    assert any(row["field"] == "citation" for row in status["suggestions"])
    assert api.get("/api/v1/research-items/" + item["id"]).json()["citation"] == ""


def test_text_upload_validation_rejects_binary_and_non_utf8(monkeypatch):
    from app.services import document_storage
    from fastapi import HTTPException

    class FakeS3:
        payload = "മലയാളം source".encode("utf-8")

        def head_object(self, **kwargs):
            return {"ContentLength": len(self.payload)}

        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(self.payload)}

    fake = FakeS3()
    monkeypatch.setattr(document_storage, "client", lambda: fake)
    assert document_storage.verify_object(
        "private", "text/plain", len(fake.payload), None
    )
    for value in (b"\x00binary", b"\xff\xfetext"):
        fake.payload = value
        with pytest.raises(HTTPException) as error:
            document_storage.verify_object("private", "text/plain", len(value), None)
        assert error.value.status_code == 422

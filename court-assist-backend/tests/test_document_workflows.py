import os
import io
import uuid
import zipfile
from datetime import date
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")
import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app import models
from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.api.v1.dependencies import current_user
from app.models.user import User
from app.models.client import Client
from app.models.finance import Receipt
from app.services import document_storage
from app.services.finance_documents import render_pdf
from app.services.draft_generation import pdf, docx, safe_html


def test_actual_pdf_unicode_and_docx_formatting(tmp_path):
    content = "<h1>സത്യവാങ്മൂലം</h1><p><b>English</b> മലയാളം</p><table><tr><td>ഫീസ്</td><td>1000.25</td></tr></table>"
    snapshot = {
        "kind": "Invoice",
        "number": "INV-TEST",
        "advocate": "അഭിഭാഷകൻ അനിൽ",
        "client": "കക്ഷി: രാജൻ",
        "date": "2026-11-05",
        "rows": [("നിയമോപദേശ ഫീസ്", "1000.25")],
        "total": "1000.25",
    }
    for name, data in [("invoice", render_pdf(snapshot)), ("draft", pdf(content))]:
        path = tmp_path / (name + ".pdf")
        path.write_bytes(data)
        with pymupdf.open(path) as document:
            assert len(document) >= 1
            fonts = [font for font in document[0].get_fonts() if "Malayalam" in font[3]]
            assert fonts and len(document.extract_font(fonts[0][0])[3]) > 1000
            assert "1000.25" in document[0].get_text()
            assert document[0].get_pixmap().width > 500
    output = docx(content)
    with zipfile.ZipFile(io.BytesIO(output)) as archive:
        xml = archive.read("word/document.xml").decode()
        assert "മലയാളം" in xml and "w:tbl" in xml and "w:b" in xml
    assert "onclick" not in safe_html('<p onclick="bad()">Safe</p>')
    assert len(pymupdf.open(stream=pdf("<p>Paragraph</p>" * 1000), filetype="pdf")) > 1


def test_invoice_receipt_private_storage_draft_versions_and_ownership(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            id=uuid.uuid4(),
            full_name="Advocate One",
            password_hash="unused",
            address="Kerala",
        )
        other = User(id=uuid.uuid4(), full_name="Advocate Two", password_hash="unused")
        db.add_all([user, other])
        db.flush()
        client = Client(
            user_id=user.id,
            client_type="Individual",
            full_name="Client One",
            phone_number="9999999999",
            address="Kochi",
            city="Kochi",
            district="Ernakulam",
            state="Kerala",
            postal_code="682001",
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        db.refresh(user)
        db.refresh(other)
        client_id = str(client.id)

    def session_override():
        with Session(engine) as db:
            yield db

    class MemoryS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, Bucket, Key, Body, **kwargs):
            self.objects[Key] = Body

        def head_object(self, Bucket, Key):
            return {"ContentLength": len(self.objects[Key])}

        def get_object(self, Bucket, Key):
            return {"Body": io.BytesIO(self.objects[Key])}

        def delete_object(self, Bucket, Key):
            self.objects.pop(Key, None)

        def generate_presigned_url(self, *args, **kwargs):
            return "https://private.example.invalid/signed"

    storage = MemoryS3()
    monkeypatch.setattr(document_storage, "client", lambda: storage)
    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app) as api:
            agreement = api.post(
                "/api/v1/fee-agreements",
                json={"client_id": client_id, "amount": "100.10"},
            )
            assert agreement.status_code == 200, agreement.text
            agreement_id = agreement.json()["id"]
            invoice = api.post(
                "/api/v1/invoices",
                json={
                    "client_id": client_id,
                    "agreement_id": agreement_id,
                    "lines": [
                        {
                            "description": "Consultation",
                            "quantity": "1",
                            "unit_price": "100.10",
                        }
                    ],
                },
            )
            assert invoice.status_code == 201, invoice.text
            invoice_id = invoice.json()["id"]
            assert (
                api.post(f"/api/v1/invoices/{invoice_id}/issue").json()["status"]
                == "issued"
            )
            assert api.get(f"/api/v1/invoices/{invoice_id}/pdf").status_code == 200
            payment = {
                "client_id": client_id,
                "agreement_id": agreement_id,
                "amount": "100.10",
                "status": "received",
            }
            paid = api.post(
                "/api/v1/payments",
                json=payment,
                headers={"Idempotency-Key": "payment-check-001"},
            )
            assert paid.status_code == 200, paid.text
            payment_id = paid.json()["id"]
            assert (
                api.post(
                    "/api/v1/payments",
                    json=payment,
                    headers={"Idempotency-Key": "payment-check-001"},
                ).json()["id"]
                == payment_id
            )
            assert (
                api.post(
                    "/api/v1/payments",
                    json={**payment, "amount": "99.00"},
                    headers={"Idempotency-Key": "payment-check-001"},
                ).status_code
                == 409
            )
            assert (
                api.patch(
                    f"/api/v1/fee-agreements/{agreement_id}",
                    json={
                        "amount": "150.10",
                        "description": "Revised agreement",
                        "status": "active",
                    },
                ).status_code
                == 422
            )
            assert (
                api.patch(
                    f"/api/v1/fee-agreements/{agreement_id}",
                    json={
                        "amount": "150.10",
                        "description": "Revised agreement",
                        "status": "active",
                        "reason": "Advocate confirmed a new agreed fee",
                    },
                ).status_code
                == 200
            )
            assert (
                api.get(f"/api/v1/fee-agreements/{agreement_id}/history").json()[0][
                    "previous"
                ]["amount"]
                == "100.10"
            )
            assert api.get(f"/api/v1/invoices/{invoice_id}").json()["status"] == "paid"
            receipt = api.get(f"/api/v1/payments/{payment_id}/receipt")
            assert receipt.status_code == 200, receipt.text
            assert (
                api.get(f"/api/v1/payments/{payment_id}/receipt").json()["number"]
                == receipt.json()["number"]
            )
            assert (
                api.post(
                    f"/api/v1/payments/{payment_id}/reverse",
                    json={"reason": "Incorrect received entry"},
                ).status_code
                == 200
            )
            assert (
                api.get(f"/api/v1/invoices/{invoice_id}").json()["status"] == "issued"
            )
            assert (
                api.get(f"/api/v1/payments/{payment_id}/receipt").json()[
                    "payment_status"
                ]
                == "reversed"
            )
            pending = api.post(
                "/api/v1/payments",
                json={**payment, "status": "pending"},
                headers={"Idempotency-Key": "pending-check-001"},
            ).json()
            assert (
                api.get(f"/api/v1/payments/{pending['id']}/receipt").status_code == 409
            )
            expense = api.post(
                "/api/v1/expenses",
                json={
                    "amount": "100.00",
                    "category": "Travel",
                    "expense_date": str(date.today()),
                },
            )
            assert expense.status_code == 200, expense.text
            assert (
                api.post(
                    f"/api/v1/expenses/{expense.json()['id']}/adjust",
                    json={"amount": "-20.01", "reason": "Receipt correction"},
                ).status_code
                == 200
            )
            report = api.get("/api/v1/finance/reports").json()
            assert (
                report["summary"]["expenses"] == "79.99"
                and report["summary"]["received"] == "0.00"
            )
            assert (
                report["by_category"]["Travel"] == "79.99"
                and report["annual"][str(date.today().year)]["expenses"] == "79.99"
            )
            draft_expense = api.post(
                "/api/v1/expenses", json={"amount": "1000.00", "status": "draft"}
            ).json()
            expense_path = "/api/v1/expenses/" + draft_expense["id"]
            assert api.get("/api/v1/finance/summary").json()["expenses"] == "79.99"
            assert (
                api.post(
                    expense_path + "/adjust",
                    json={"amount": "1", "reason": "Not confirmed yet"},
                ).status_code
                == 409
            )
            assert (
                api.post(
                    expense_path + "/confirm",
                    json={"reason": "Checked receipt details"},
                ).status_code
                == 200
            )
            assert api.get("/api/v1/finance/summary").json()["expenses"] == "1079.99"
            assert api.delete(expense_path).status_code == 409
            assert api.post(expense_path + "/archive").status_code == 200
            assert api.get("/api/v1/finance/summary").json()["expenses"] == "1079.99"
            assert (
                api.post(
                    f"/api/v1/payments/{pending['id']}/confirm",
                    json={"reason": "Bank receipt verified"},
                ).status_code
                == 200
            )
            assert (
                api.post(
                    f"/api/v1/payments/{pending['id']}/confirm",
                    json={"reason": "Repeated confirmation"},
                ).status_code
                == 409
            )
            assert api.get("/api/v1/finance/summary").json()["received"] == "100.10"
            assert api.post("/api/v1/finance/report-pdf").status_code == 200
            draft = api.post(
                "/api/v1/draft-documents",
                json={
                    "title": "Draft A",
                    "content": "<p>Original</p>",
                    "client_id": client_id,
                },
            )
            assert draft.status_code == 200, draft.text
            draft_id = draft.json()["id"]
            revision = draft.json()["updated_at"]
            edited = api.patch(
                f"/api/v1/draft-documents/{draft_id}",
                json={"content": "<p>Changed</p>", "expected_updated_at": revision},
            )
            assert edited.status_code == 200, edited.text
            assert (
                api.patch(
                    f"/api/v1/draft-documents/{draft_id}",
                    json={"content": "Overwrite", "expected_updated_at": revision},
                ).status_code
                == 409
            )
            for file_format in ("pdf", "docx"):
                exported = api.post(
                    f"/api/v1/draft-documents/{draft_id}/export",
                    json={"file_format": file_format},
                )
                assert exported.status_code == 201, exported.text
            versions = api.get(f"/api/v1/draft-documents/{draft_id}/versions").json()
            restored = api.post(
                f"/api/v1/draft-documents/{draft_id}/versions/{versions[-1]['id']}/restore"
            )
            assert restored.status_code == 200, restored.text
            assert (
                api.get(f"/api/v1/draft-documents/{draft_id}/exports").status_code
                == 200
            )
            app.dependency_overrides[current_user] = lambda: other
            for path in (
                f"/invoices/{invoice_id}",
                f"/invoices/{invoice_id}/pdf",
                f"/payments/{payment_id}/receipt",
                f"/draft-documents/{draft_id}/exports",
            ):
                assert api.get("/api/v1" + path).status_code == 404, path
            assert (
                api.post(
                    "/api/v1/invoices",
                    json={
                        "client_id": client_id,
                        "lines": [{"description": "Unauthorized", "unit_price": "1"}],
                    },
                ).status_code
                == 404
            )
            assert len(storage.objects) == 5
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

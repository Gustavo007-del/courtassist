"""Generate fixed financial snapshots and publish them through the existing vault."""

import hashlib
import html
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import pymupdf
from fastapi import HTTPException
from app.models.document import Document, DocumentVersion, DocumentAccessLog
from app.services import document_storage as storage
from app.core.config import get_settings


def total(lines):
    return sum(
        (
            (
                Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"]))
            ).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            for line in lines
        ),
        Decimal("0.00"),
    )


def render_pdf(snapshot):
    def esc(value):
        return html.escape(str(value or ""))

    title = esc(snapshot["kind"])
    number = esc(snapshot["number"])
    rows = "".join(
        f"<tr><td>{esc(line[0])}</td><td>{esc(line[1])}</td></tr>"
        for line in snapshot["rows"]
    )
    markup = f"""<html><body><h1>{title}</h1><p>{number}</p><h3>{esc(snapshot["advocate"])}</h3><p>{esc(snapshot.get("address"))}</p><hr><p>{esc(snapshot["client"])}</p><p>{esc(snapshot.get("case"))}</p><p>{esc(snapshot["date"])}</p><table><tr><th>Description</th><th>INR</th></tr>{rows}</table><h2>Total INR {esc(snapshot["total"])}</h2><p>{esc(snapshot.get("terms"))}</p><p>{esc(snapshot.get("status"))}</p></body></html>"""
    story = pymupdf.Story(
        markup,
        user_css="body{font-family:serif;font-size:11pt;line-height:1.5}h1{color:#162a42}td,th{padding:9pt;text-align:left}table{width:100%;border-spacing:0}th{background:#e9edf2}h2{font-size:15pt}",
    )
    stream = io.BytesIO()
    writer = pymupdf.DocumentWriter(stream)
    try:
        for _ in range(100):
            device = writer.begin_page(pymupdf.paper_rect("a4"))
            more, _ = story.place(pymupdf.Rect(48, 48, 547, 785))
            story.draw(device)
            writer.end_page()
            if not more:
                break
        else:
            raise HTTPException(422, "Financial document exceeds page limit")
    finally:
        writer.close()
    doc = pymupdf.open(stream=stream.getvalue(), filetype="pdf")
    for page in doc:
        page.insert_text((48, 817), f"{page.number + 1} / {len(doc)}", fontsize=9)
    return doc.tobytes(garbage=4, deflate=True)


def store_generated(
    db, user_id, data, filename, case_id=None, client_id=None, category="Other"
):
    extension = "." + filename.rsplit(".", 1)[-1].lower()
    mime_type = (
        "application/pdf"
        if extension == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    storage.validate_file(filename, mime_type, len(data))
    doc_id, version_id = uuid.uuid4(), uuid.uuid4()
    key = storage.storage_key(user_id, doc_id, version_id, extension, "stored")
    checksum = hashlib.sha256(data).hexdigest()
    settings = get_settings()
    s3 = storage.client()
    try:
        s3.put_object(
            Bucket=settings.document_s3_bucket,
            Key=key,
            Body=data,
            ContentType=mime_type,
        )
        storage.verify_object(key, mime_type, len(data), checksum)
        doc = Document(
            id=doc_id,
            user_id=user_id,
            case_id=case_id,
            client_id=client_id,
            document_name=filename,
            original_filename=filename,
            file_extension=extension,
            mime_type=mime_type,
            file_size=len(data),
            document_category=category,
            storage_key=key,
            storage_status="cloud_stored",
            checksum=checksum,
            current_version_id=version_id,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()
        db.add(
            DocumentVersion(
                id=version_id,
                document_id=doc_id,
                user_id=user_id,
                version_number=1,
                storage_key=key,
                original_filename=filename,
                file_size=len(data),
                checksum=checksum,
                storage_status="cloud_stored",
                change_description="Generated financial snapshot",
            )
        )
        db.add(
            DocumentAccessLog(
                document_id=doc_id, user_id=user_id, action="generated_export"
            )
        )
        db.flush()
        return doc
    except Exception:
        try:
            s3.delete_object(Bucket=settings.document_s3_bucket, Key=key)
        except Exception:
            pass
        raise HTTPException(503, "Could not store the private generated document")


def publish(db, user_id, snapshot, case_id=None, client_id=None):
    category = (
        "Receipts"
        if snapshot["kind"] == "Payment receipt"
        else "Invoices"
        if snapshot["kind"] == "Invoice"
        else "Other"
    )
    return store_generated(
        db,
        user_id,
        render_pdf(snapshot),
        f"{snapshot['number']}.pdf",
        case_id,
        client_id,
        category,
    )

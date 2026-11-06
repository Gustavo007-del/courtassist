"""Resolve exactly the selected resources. Case selection never expands to related records."""

import re
from dataclasses import asdict, dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.models.case import Case, CaseActivity, CaseStatusHistory
from app.models.diary import CaseDiaryEntry
from app.models.document import Document, DocumentOCR, DocumentVersion
from app.models.hearing import Hearing
from app.models.phase10 import ResearchItem
from app.models.planning import Task
from app.services import document_ocr, document_storage
from app.services.ai_provider import AIError


@dataclass
class Passage:
    kind: str
    id: str
    title: str
    text: str
    page: int | None = None
    paragraph: str | None = None
    version: str | None = None
    reference: str | None = None

    def citation(self):
        values = asdict(self)
        del values["text"]
        return values


MODELS = {
    "case": Case, "document": Document, "diary": CaseDiaryEntry, "hearing": Hearing,
    "timeline": CaseActivity, "status": CaseStatusHistory, "research": ResearchItem, "task": Task,
}

FIELDS = {
    "case": ("case_title", "case_number", "filing_date", "registration_date", "current_status", "case_stage", "description"),
    "diary": ("entry_date", "entry_type", "title", "content", "proceedings_summary", "judge_directions",
              "arguments_summary", "observations", "next_action", "follow_up_date"),
    "hearing": ("hearing_date", "hearing_time", "status", "purpose", "proceedings_notes", "judge_directions",
                "adjournment_reason", "outcome", "next_hearing_date"),
    "timeline": ("created_at", "activity_type", "title", "description"),
    "status": ("effective_date", "previous_status", "new_status", "reason"),
    "research": ("title", "citation", "verification_status", "court", "case_number", "judgment_date", "full_text", "summary", "notes"),
    "task": ("title", "status", "due_date", "due_time", "description"),
}


def owned(db, model, owner, identifier, lock=False):
    query = select(model).where(model.id == identifier, model.user_id == owner)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def resolve(db, owner, selection, case_id):
    kind = selection["kind"]
    row = owned(db, MODELS[kind], owner, UUID(selection["id"]))
    linked_case = row.id if kind == "case" else row.case_id
    if linked_case and kind not in ("case", "research"):
        owned(db, Case, owner, linked_case)
    if case_id and kind != "research" and linked_case != case_id:
        raise HTTPException(422, "Selected records must belong to the selected case")
    if getattr(row, "is_archived", False) or getattr(row, "archived_at", None):
        raise HTTPException(409, "Selected record is archived")
    return row


def pin_sources(db, owner, selections, case_id):
    output = []
    for selection in selections:
        row = resolve(db, owner, selection, case_id)
        if selection["kind"] == "document":
            version = owned(db, DocumentVersion, owner, row.current_version_id)
            if version.document_id != row.id or version.storage_status not in ("stored", "cloud_stored"):
                raise HTTPException(409, "Selected document version is unavailable")
            output.append({**selection, "version": str(version.id)})
        else:
            stamp = getattr(row, "updated_at", row.created_at)
            output.append({**selection, "revision": stamp.replace(tzinfo=None).isoformat()})
    return output


def read_pages(db, owner, row, selection):
    version_id = UUID(selection["version"])
    version = owned(db, DocumentVersion, owner, version_id)
    if version.document_id != row.id or version.storage_status not in ("stored", "cloud_stored"):
        raise AIError("source_changed")
    ocr = db.scalar(select(DocumentOCR).where(
        DocumentOCR.user_id == owner, DocumentOCR.document_id == row.id,
        DocumentOCR.document_version_id == version_id, DocumentOCR.processing_status.in_(["completed", "needs_review"]),
    ).order_by(DocumentOCR.processed_at.desc()).limit(1))
    if ocr and ocr.page_results and any(page.get("extracted_text", "").strip() for page in ocr.page_results):
        return ocr.page_results
    settings = get_settings()
    try:
        response = document_storage.client().get_object(Bucket=settings.document_s3_bucket, Key=version.storage_key)
        with response["Body"] as stream:
            data = stream.read(settings.document_max_bytes + 1)
        if len(data) > settings.document_max_bytes:
            raise AIError("source_too_large")
        provider = "tesseract" if settings.ocr_provider == "tesseract" else "pypdf"
        return document_ocr.extract_pages(data, row.mime_type, provider)
    except AIError:
        raise
    except Exception:
        raise AIError("source_text_unavailable") from None


def split_passages(text):
    # Prefer paragraph and sentence boundaries while keeping single long lines bounded.
    text = text.strip()
    while len(text) > 1000:
        candidates = [text.rfind(delimiter, 550, 1001) for delimiter in ("\n\n", "\n", ". ", " ")]
        boundary = next((index + 1 for index in candidates if index >= 0), 1000)
        yield text[:boundary].strip()
        # Small overlap preserves evidence across the split without moving to another page.
        start = text.rfind(" ", max(1, boundary - 90), boundary - 1)
        text = text[(start + 1 if start >= 0 else boundary):].strip()
    if text:
        yield text


def load_passages(db, owner, selections, case_id):
    passages = []
    warnings = []
    total = 0
    cap = get_settings().ai_max_source_chars
    for selected in selections:
        row = resolve(db, owner, selected, case_id)
        kind = selected["kind"]
        if kind == "document":
            pages = read_pages(db, owner, row, selected)
            if selected.get("first_page") is not None:
                first, last = selected["first_page"], selected["last_page"]
                pages = [page for page in pages if isinstance(page.get("page_number"), int) and first <= page["page_number"] <= last]
            if not pages or not any(page.get("extracted_text", "").strip() for page in pages):
                raise AIError("ocr_required")
            if any(not page.get("extracted_text", "").strip() or (
                isinstance(page.get("confidence_score"), (int, float)) and page["confidence_score"] < 0.6
            ) for page in pages):
                warnings.append("partial_ocr")
            for page in pages:
                text = page.get("extracted_text", "").strip()
                total += len(text)
                if total > cap:
                    raise AIError("source_too_large")
                passages.extend(Passage(kind, str(row.id), row.document_name, part, page=page.get("page_number"),
                                        version=selected["version"]) for part in split_passages(text))
        else:
            stamp = getattr(row, "updated_at", row.created_at)
            if stamp.replace(tzinfo=None).isoformat() != selected["revision"]:
                raise AIError("source_changed")
            text = "\n".join(f"{field}: {getattr(row, field)}" for field in FIELDS[kind] if getattr(row, field) is not None and getattr(row, field) != "")
            total += len(text)
            if total > cap:
                raise AIError("source_too_large")
            title = getattr(row, "title", None) or getattr(row, "case_title", None) or kind
            passages.extend(Passage(kind, str(row.id), title, part, paragraph=getattr(row, "paragraph_reference", None),
                                    reference=getattr(row, "page_reference", None)) for part in split_passages(text))
        if len(passages) > 160:
            raise AIError("source_too_large")
    if not passages:
        raise AIError("source_text_unavailable")
    return passages, sorted(set(warnings))


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


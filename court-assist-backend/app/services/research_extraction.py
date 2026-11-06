from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.phase10 import ResearchItem
from app.models.document import Document, DocumentOCR
from app.models.research import ResearchSourceMetadata
from app.services import research_service as service
from app.services.document_ocr import suggestions

FIELDS = [
    "case_title",
    "court",
    "case_number",
    "cnr_number",
    "judgment_date",
    "citation",
    "party_information",
    "act_name",
    "section_number",
]


def start(db, user, item):
    if not item.document_id:
        raise HTTPException(409, "Link an uploaded private document first")
    doc = service.owned(db, Document, item.document_id, user.id)
    db.scalar(
        select(Document)
        .where(Document.id == doc.id, Document.user_id == user.id)
        .with_for_update()
    )
    from app.api.v1.documents import start_ocr

    record = start_ocr(doc.id, db, user)
    source = db.scalar(
        select(ResearchSourceMetadata).where(
            ResearchSourceMetadata.item_id == item.id,
            ResearchSourceMetadata.version_id == record.document_version_id,
            ResearchSourceMetadata.user_id == user.id,
        )
    )
    if not source:
        source = ResearchSourceMetadata(
            user_id=user.id,
            item_id=item.id,
            document_id=doc.id,
            version_id=record.document_version_id,
            ocr_id=record.id,
        )
        db.add(source)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            source = db.scalar(
                select(ResearchSourceMetadata).where(
                    ResearchSourceMetadata.item_id == item.id,
                    ResearchSourceMetadata.version_id == record.document_version_id,
                    ResearchSourceMetadata.user_id == user.id,
                )
            )
            if not source:
                raise HTTPException(409, "Extraction changed; refresh and retry")
        service.audit(
            db,
            user.id,
            "extraction_requested",
            item=item,
            details={
                "document_id": str(doc.id),
                "version_id": str(record.document_version_id),
            },
        )
        db.commit()
    return status(db, user.id, item)


def status(db, user_id, item):
    if not item.document_id:
        return {
            "processing_status": "no_document",
            "suggestions": [],
            "unavailable_fields": FIELDS,
        }
    doc = service.owned(db, Document, item.document_id, user_id)
    source = db.scalar(
        select(ResearchSourceMetadata).where(
            ResearchSourceMetadata.user_id == user_id,
            ResearchSourceMetadata.item_id == item.id,
            ResearchSourceMetadata.version_id == doc.current_version_id,
            ResearchSourceMetadata.document_id == doc.id,
        )
    )
    if not source:
        failed = db.scalar(
            select(DocumentOCR).where(
                DocumentOCR.document_id == doc.id,
                DocumentOCR.document_version_id == doc.current_version_id,
                DocumentOCR.user_id == user_id,
                DocumentOCR.processing_status == "failed",
            )
        )
        if failed:
            return {
                "processing_status": "failed",
                "error_message": failed.error_message,
                "suggestions": [],
                "unavailable_fields": FIELDS,
            }
        return {
            "processing_status": "not_started",
            "suggestions": [],
            "unavailable_fields": FIELDS,
        }
    record = service.owned(db, DocumentOCR, source.ocr_id, user_id)
    if (
        record.processing_status in ("completed", "needs_review")
        and not source.suggestions
    ):
        mapped = []
        mapping = {
            "court_name": "court",
            "order_date": "judgment_date",
            "petitioner": "party_information",
            "respondent": "party_information",
        }
        for proposed in suggestions(record.page_results):
            field = mapping.get(proposed["field"], proposed["field"])
            if field not in FIELDS:
                continue
            value = proposed["value"]
            if field == "judgment_date":
                try:
                    value = (
                        datetime.strptime(
                            value.replace(".", "/").replace("-", "/"), "%d/%m/%Y"
                        )
                        .date()
                        .isoformat()
                    )
                except ValueError:
                    continue
            if proposed["field"] in ("petitioner", "respondent"):
                value = proposed["field"].title() + ": " + value
            mapped.append({**proposed, "field": field, "value": value})
        source.suggestions = mapped
        db.commit()
    return {
        "metadata_id": str(source.id),
        "document_id": str(doc.id),
        "version_id": str(source.version_id),
        "processing_status": record.processing_status,
        "error_message": record.error_message,
        "suggestions": source.suggestions,
        "reviewed": source.reviewed,
        "unavailable_fields": [
            field
            for field in FIELDS
            if field not in {proposal["field"] for proposal in source.suggestions}
        ],
        "notice": "Extracted values are unverified suggestions. Confirm or edit them before use.",
    }


def confirm(db, user, item, request):
    source = service.owned(db, ResearchSourceMetadata, request.metadata_id, user.id)
    if source.item_id != item.id or source.document_id != item.document_id:
        raise HTTPException(404, "Source metadata not found")
    doc = service.owned(db, Document, source.document_id, user.id)
    if doc.current_version_id != source.version_id:
        raise HTTPException(
            409,
            "Document version changed; extract the current version before reviewing",
        )
    record = service.owned(db, DocumentOCR, source.ocr_id, user.id)
    if record.processing_status not in ("completed", "needs_review"):
        raise HTTPException(409, "Extraction is not complete")
    available = {
        (proposal["field"], proposal["value"]) for proposal in source.suggestions
    }
    changes = {}
    reviewed = []
    for choice in request.choices:
        if (choice.field, choice.source_value) not in available:
            raise HTTPException(422, "Suggestion is unavailable")
        if choice.status == "accepted" and choice.value != choice.source_value:
            raise HTTPException(422, "Use edited status for a changed value")
        if choice.status != "rejected":
            if choice.field in changes:
                raise HTTPException(422, "Choose one reviewed value per field")
            changes[choice.field] = choice.value
        reviewed.append(
            {
                **choice.model_dump(),
                "source_evidence": [
                    proposal
                    for proposal in source.suggestions
                    if proposal["field"] == choice.field
                    and proposal["value"] == choice.source_value
                ],
                "reviewed_at": service.now().isoformat(),
                "reviewed_by": str(user.id),
            }
        )
    if changes:
        changes["verification_status"] = "unverified"
        values = service.item_values(item, changes)
        service.save_item(db, user.id, values, row=item)
        item.source_status = "document_extracted"
    source.reviewed = [*source.reviewed, *reviewed]
    source.reviewed_at = service.now()
    service.audit(
        db,
        user.id,
        "metadata_reviewed",
        item=item,
        details={"metadata_id": str(source.id), "applied_fields": list(changes)},
    )
    db.commit()
    return service.data(item)

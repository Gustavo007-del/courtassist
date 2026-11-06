import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, delete, exists, or_, func, literal_column
from sqlalchemy.exc import IntegrityError
from app.models.phase10 import ResearchItem
from app.models.research import (
    ResearchTag,
    ResearchItemTag,
    ResearchNote,
    ResearchNoteTag,
    ResearchCaseLink,
    ResearchAudit,
    ResearchImportBatch,
)
from app.models.case import Case
from app.models.client import Client
from app.models.document import Document, DocumentOCR
from app.schemas.research import ResearchInput, NoteInput
from app.services.research_search import SEARCH_COLUMNS, SEARCH_SQL


def now():
    return datetime.now(timezone.utc)


def owned(db, model, identifier, user_id, lock=False):
    query = select(model).where(model.id == identifier, model.user_id == user_id)
    row = db.scalar(query.with_for_update() if lock else query) if identifier else None
    if not row:
        raise HTTPException(404, "Research or linked record not found")
    return row


def data(row, brief=False):
    result = {
        column.name: getattr(row, column.name) for column in row.__table__.columns
    }
    if brief:
        for name in ("full_text", "notes", "party_information"):
            result.pop(name, None)
        if "summary" in result:
            result["summary"] = result["summary"][:500]
        if isinstance(row, ResearchNote):
            for name in ("content", "quoted_text", "references"):
                result.pop(name, None)
    return result


def audit(db, user_id, action, item=None, note=None, details=None):
    db.add(
        ResearchAudit(
            user_id=user_id,
            item_id=item.id if item else None,
            note_id=note.id if note else None,
            action=action,
            details=details or {},
        )
    )


def validate_links(db, user_id, values):
    for key, model in [
        ("case_id", Case),
        ("client_id", Client),
        ("document_id", Document),
        ("item_id", ResearchItem),
    ]:
        if values.get(key):
            row = owned(db, model, values[key], user_id)
            if key == "document_id" and (
                not row.current_version_id
                or row.storage_status not in ("stored", "cloud_stored", "archived")
            ):
                raise HTTPException(
                    409, "Finish the private document upload before linking it"
                )


def tag_for(db, user_id, name):
    normalized = name.strip().casefold()
    tag = db.scalar(
        select(ResearchTag)
        .where(
            ResearchTag.user_id == user_id, ResearchTag.normalized_name == normalized
        )
        .with_for_update()
    )
    if not tag:
        try:
            with db.begin_nested():
                tag = ResearchTag(
                    user_id=user_id, name=name.strip(), normalized_name=normalized
                )
                db.add(tag)
                db.flush()
        except IntegrityError:
            tag = db.scalar(
                select(ResearchTag).where(
                    ResearchTag.user_id == user_id,
                    ResearchTag.normalized_name == normalized,
                )
            )
            if not tag:
                raise
    return tag


def set_tags(db, row, names):
    association = ResearchItemTag if isinstance(row, ResearchItem) else ResearchNoteTag
    key = "item_id" if isinstance(row, ResearchItem) else "note_id"
    db.flush()
    db.execute(delete(association).where(getattr(association, key) == row.id))
    tags = []
    seen = set()
    for name in names:
        tag = tag_for(db, row.user_id, name)
        if tag.id in seen:
            continue
        seen.add(tag.id)
        tags.append(tag.name)
        db.add(association(**{key: row.id, "tag_id": tag.id}))
    row.tags = tags


def item_values(row, changes):
    values = {name: getattr(row, name) for name in ResearchInput.model_fields}
    values["source_status"] = "manually_entered"
    values.update(changes)
    try:
        return ResearchInput.model_validate(values).model_dump()
    except ValidationError as error:
        raise HTTPException(422, error.errors()[0]["msg"])


def save_item(db, user_id, values, row=None, origin=None):
    validate_links(db, user_id, values)
    creating = row is None
    if creating:
        row = ResearchItem(user_id=user_id)
        db.add(row)
    before = (
        {
            key: str(getattr(row, key) or "")
            for key in (
                "citation",
                "court",
                "case_number",
                "cnr_number",
                "source_name",
                "source_url",
                "document_id",
                "verification_status",
            )
        }
        if not creating
        else {}
    )
    tags = values.pop("tags", [])
    values.pop("source_status", None)
    old_case = row.case_id
    for key, value in values.items():
        setattr(row, key, value)
    if creating:
        row.source_status = origin or "manually_entered"
    row.updated_at = now()
    db.flush()
    set_tags(db, row, tags)
    if old_case and old_case != row.case_id:
        db.execute(
            delete(ResearchCaseLink).where(
                ResearchCaseLink.item_id == row.id, ResearchCaseLink.case_id == old_case
            )
        )
    if row.case_id and not db.get(ResearchCaseLink, (row.id, row.case_id)):
        db.add(ResearchCaseLink(item_id=row.id, case_id=row.case_id))
    audit(
        db,
        user_id,
        "created" if creating else "edited",
        item=row,
        details={"previous_metadata": before, "changed_fields": list(values)},
    )
    return row


def search_query(
    db,
    user_id,
    q="",
    item_type=None,
    court=None,
    from_date=None,
    to_date=None,
    language=None,
    tag=None,
    favorite=None,
    case_id=None,
    archived=False,
):
    query = select(ResearchItem).where(
        ResearchItem.user_id == user_id,
        ResearchItem.archived_at.is_not(None)
        if archived
        else ResearchItem.archived_at.is_(None),
    )
    if q:
        term = "%" + q + "%"
        if db.bind.dialect.name == "postgresql":
            text_match = func.to_tsvector(
                literal_column("'simple'"), literal_column(SEARCH_SQL)
            ).op("@@")(func.plainto_tsquery("simple", q))
        else:
            text_match = or_(
                *(
                    getattr(ResearchItem, column).ilike(term)
                    for column in SEARCH_COLUMNS
                )
            )
        tag_match = exists(
            select(ResearchItemTag.item_id)
            .join(ResearchTag, ResearchTag.id == ResearchItemTag.tag_id)
            .where(
                ResearchItemTag.item_id == ResearchItem.id,
                ResearchTag.user_id == user_id,
                ResearchTag.name.ilike(term),
            )
        )
        ocr_text = DocumentOCR.extracted_text.ilike(term)
        if db.bind.dialect.name == "postgresql":
            ocr_text = func.to_tsvector("simple", DocumentOCR.extracted_text).op("@@")(
                func.plainto_tsquery("simple", q)
            )
        doc_match = exists(
            select(DocumentOCR.id)
            .join(Document, Document.id == DocumentOCR.document_id)
            .where(
                Document.id == ResearchItem.document_id,
                Document.user_id == user_id,
                DocumentOCR.user_id == user_id,
                DocumentOCR.document_version_id == Document.current_version_id,
                DocumentOCR.processing_status.in_(["completed", "needs_review"]),
                ocr_text,
            )
        )
        query = query.where(
            or_(
                text_match,
                ResearchItem.citation.ilike(term),
                ResearchItem.case_number.ilike(term),
                tag_match,
                doc_match,
            )
        )
    for column, value in [
        ("item_type", item_type),
        ("court", court),
        ("language", language),
    ]:
        if value:
            query = query.where(getattr(ResearchItem, column) == value)
    if from_date:
        query = query.where(ResearchItem.judgment_date >= from_date)
    if to_date:
        query = query.where(ResearchItem.judgment_date <= to_date)
    if favorite is not None:
        query = query.where(ResearchItem.favorite == favorite)
    if tag:
        query = query.where(
            exists(
                select(ResearchItemTag.item_id)
                .join(ResearchTag, ResearchTag.id == ResearchItemTag.tag_id)
                .where(
                    ResearchItemTag.item_id == ResearchItem.id,
                    ResearchTag.user_id == user_id,
                    ResearchTag.normalized_name == tag.strip().casefold(),
                )
            )
        )
    if case_id:
        query = query.where(
            or_(
                ResearchItem.case_id == case_id,
                exists(
                    select(ResearchCaseLink.item_id).where(
                        ResearchCaseLink.item_id == ResearchItem.id,
                        ResearchCaseLink.case_id == case_id,
                    )
                ),
            )
        )
    return query


CSV_FIELDS = {
    "title",
    "item_type",
    "court",
    "case_number",
    "cnr_number",
    "citation",
    "case_title",
    "judgment_date",
    "source_name",
    "source_url",
    "accessed_date",
    "summary",
    "full_text",
    "language",
    "act_name",
    "section_number",
    "subject",
    "notes",
    "tags",
    "page_reference",
    "paragraph_reference",
}


def duplicate_key(values):
    if values.get("citation", "").strip():
        return ("citation", values["citation"].strip().casefold())
    if values.get("source_url"):
        return ("url", values["source_url"].strip())
    return (
        "title",
        values["title"].strip().casefold(),
        values.get("court", "").strip().casefold(),
    )


def existing_keys(db, user_id):
    return {
        duplicate_key(dict(row._mapping))
        for row in db.execute(
            select(
                ResearchItem.title,
                ResearchItem.citation,
                ResearchItem.source_url,
                ResearchItem.court,
            ).where(ResearchItem.user_id == user_id)
        ).all()
    }


def preview_import(db, user_id, csv_text):
    rows = []
    errors = []
    seen = existing_keys(db, user_id)
    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")), strict=True)
        columns = reader.fieldnames or []
        if (
            "title" not in columns
            or len(set(columns)) != len(columns)
            or set(columns) - CSV_FIELDS
        ):
            raise ValueError(
                "CSV requires a title column, unique headers, and only supported column names"
            )
        for index, raw in enumerate(reader, 2):
            if index > 501:
                raise ValueError("A batch may contain at most 500 records")
            try:
                if None in raw:
                    raise ValueError("Row has more values than column headers")
                values = {
                    key: value for key, value in raw.items() if value not in (None, "")
                }
                if "tags" in values:
                    values["tags"] = [
                        tag.strip() for tag in values["tags"].split("|") if tag.strip()
                    ]
                values = ResearchInput.model_validate(values).model_dump(mode="json")
                key = duplicate_key(values)
                rows.append({"row": index, "data": values, "duplicate": key in seen})
                seen.add(key)
            except (ValidationError, ValueError) as error:
                errors.append(
                    {
                        "row": index,
                        "message": error.errors()[0]["msg"]
                        if isinstance(error, ValidationError)
                        else str(error),
                    }
                )
    except (csv.Error, ValueError) as error:
        errors.append({"row": 1, "message": str(error)})
    if not rows and not errors:
        errors.append({"row": 1, "message": "CSV contains no records"})
    batch = ResearchImportBatch(user_id=user_id, records=rows, errors=errors)
    db.add(batch)
    db.commit()
    return batch


def confirm_import(db, user_id, batch_id, allow_duplicates):
    batch = db.scalar(
        select(ResearchImportBatch)
        .where(
            ResearchImportBatch.id == batch_id, ResearchImportBatch.user_id == user_id
        )
        .with_for_update()
    )
    if not batch:
        raise HTTPException(404, "Import preview not found")
    if batch.status == "imported":
        return batch
    created = (
        batch.created_at
        if batch.created_at.tzinfo
        else batch.created_at.replace(tzinfo=timezone.utc)
    )
    if now() - created > timedelta(minutes=30):
        raise HTTPException(409, "Import preview expired; preview the CSV again")
    if batch.errors:
        raise HTTPException(422, "Correct invalid CSV rows before importing")
    seen = existing_keys(db, user_id)
    keys = [duplicate_key(row["data"]) for row in batch.records]
    duplicates = any(key in seen for key in keys) or len(set(keys)) != len(keys)
    if duplicates and not allow_duplicates:
        raise HTTPException(
            409,
            "Possible duplicates found; explicitly allow duplicates or edit and preview the CSV again",
        )
    identifiers = []
    for record in batch.records:
        values = ResearchInput.model_validate(record["data"]).model_dump()
        item = save_item(db, user_id, values, origin="imported")
        identifiers.append(str(item.id))
    batch.status = "imported"
    batch.imported_ids = identifiers
    batch.records = []
    db.commit()
    return batch

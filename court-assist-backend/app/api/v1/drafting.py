from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.api.v1.phase10 import owned, dump
from app.database.session import get_db
from app.models.user import User
from app.models.phase10 import DraftDocument
from app.models.drafting import DraftExport, DraftAudit
from app.models.document import Document
from app.schemas.practice import Input
from app.services import draft_generation
from app.services.finance_documents import store_generated
from app.services.document_storage import presigned_get

router = APIRouter(tags=["drafting-exports"])


class ExportInput(Input):
    file_format: Literal["pdf", "docx"] = "pdf"


@router.post("/draft-documents/{rid}/export", status_code=201)
def export_draft(
    rid: UUID,
    data: ExportInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(DraftDocument)
        .where(DraftDocument.id == rid, DraftDocument.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Draft not found")
    try:
        content = (
            draft_generation.pdf(row.content, row.title)
            if data.file_format == "pdf"
            else draft_generation.docx(row.content)
        )
    except ValueError:
        raise HTTPException(422, "Document exceeds export limits")
    doc = store_generated(
        db,
        user.id,
        content,
        f"draft-{row.id}.{data.file_format}",
        row.case_id,
        row.client_id,
    )
    exported = DraftExport(
        user_id=user.id,
        draft_id=row.id,
        document_id=doc.id,
        file_format=data.file_format,
    )
    row.last_exported_at = datetime.now(timezone.utc)
    db.add(exported)
    db.add(
        DraftAudit(
            user_id=user.id, draft_id=row.id, action="export_" + data.file_format
        )
    )
    db.commit()
    return {
        **dump(exported),
        "url": presigned_get(doc.storage_key, doc.original_filename),
    }


@router.get("/draft-documents/{rid}/exports")
def exports(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, DraftDocument, rid, user)
    rows = db.scalars(
        select(DraftExport)
        .where(DraftExport.draft_id == rid, DraftExport.user_id == user.id)
        .order_by(DraftExport.created_at.desc())
        .limit(100)
    ).all()
    return [dump(row) for row in rows]


@router.get("/draft-documents/{rid}/audit")
def audit(rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned(db, DraftDocument, rid, user)
    return [
        dump(row)
        for row in db.scalars(
            select(DraftAudit)
            .where(DraftAudit.draft_id == rid, DraftAudit.user_id == user.id)
            .order_by(DraftAudit.created_at.desc())
            .limit(100)
        )
    ]

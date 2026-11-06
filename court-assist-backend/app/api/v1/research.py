from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, exists, delete, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.models.case import Case
from app.models.phase10 import ResearchItem
from app.models.research import (
    ResearchTag,
    ResearchItemTag,
    ResearchNote,
    ResearchNoteTag,
    ResearchCaseLink,
    ResearchAudit,
)
from app.schemas.research import (
    ResearchInput,
    ResearchPatch,
    TagInput,
    NoteInput,
    NotePatch,
    CaseLinkInput,
    ImportInput,
    MetadataReview,
    FavoriteInput,
)
from app.services import research_service as service, research_extraction as extraction
from app.services.draft_generation import safe_html

router = APIRouter(tags=["research"])


@router.get("/research-items/search")
@router.get("/research-items")
def items(
    q: str = Query("", max_length=500),
    item_type: str | None = None,
    court: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    language: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    case_id: UUID | None = None,
    archived: bool = False,
    sort: Literal["recent", "title", "date"] = "recent",
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Invalid date range")
    query = service.search_query(
        db,
        user.id,
        q,
        item_type,
        court,
        from_date,
        to_date,
        language,
        tag,
        favorite,
        case_id,
        archived,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    ordering = {
        "recent": ResearchItem.updated_at.desc(),
        "title": ResearchItem.title.asc(),
        "date": ResearchItem.judgment_date.desc().nulls_last(),
    }[sort]
    return {
        "items": [
            service.data(row, brief=True)
            for row in db.scalars(
                query.order_by(ordering, ResearchItem.id).offset(offset).limit(limit)
            )
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/research-items", status_code=201)
def create_item(
    data: ResearchInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = service.save_item(db, user.id, data.model_dump())
    db.commit()
    return service.data(row)


@router.post("/research-items/import")
def import_records(
    data: ImportInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if data.confirm:
        if not data.batch_id:
            raise HTTPException(422, "Preview the CSV before confirming")
        batch = service.confirm_import(
            db, user.id, data.batch_id, data.allow_duplicates
        )
    else:
        batch = service.preview_import(db, user.id, data.csv_text)
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "rows": batch.records,
        "errors": batch.errors,
        "imported_ids": batch.imported_ids,
    }


@router.get("/research-items/import/sample")
def csv_sample(user: User = Depends(current_user)):
    from fastapi.responses import Response

    return Response(
        "title,item_type,citation,court,source_name,source_url,judgment_date,tags,summary\nMy private research note,Research note,,,,,,Civil procedure|Evidence,Advocate-entered summary\n",
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="research-import-sample.csv"'
        },
    )


@router.get("/research-items/{rid}")
def detail(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = service.owned(db, ResearchItem, rid, user.id)
    links = db.scalars(
        select(ResearchCaseLink.case_id)
        .join(Case, Case.id == ResearchCaseLink.case_id)
        .where(ResearchCaseLink.item_id == rid, Case.user_id == user.id)
    ).all()
    return {
        **service.data(row),
        "linked_case_ids": [str(identifier) for identifier in links],
    }


@router.patch("/research-items/{rid}")
def update_item(
    rid: UUID,
    data: ResearchPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = service.owned(db, ResearchItem, rid, user.id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    critical = {
        "citation",
        "court",
        "case_number",
        "cnr_number",
        "judgment_date",
        "source_url",
        "document_id",
        "case_title",
        "act_name",
        "section_number",
    }
    if (
        critical.intersection(changes)
        and changes.get("verification_status") != "manually_verified"
    ):
        changes["verification_status"] = "unverified"
    values = service.item_values(row, changes)
    service.save_item(db, user.id, values, row=row)
    db.commit()
    return service.data(row)


@router.delete("/research-items/{rid}")
@router.post("/research-items/{rid}/archive")
def archive_item(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = service.owned(db, ResearchItem, rid, user.id)
    row.archived_at = service.now()
    service.audit(db, user.id, "archived", item=row)
    db.commit()
    return service.data(row)


@router.post("/research-items/{rid}/restore")
def restore_item(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = service.owned(db, ResearchItem, rid, user.id)
    row.archived_at = None
    service.audit(db, user.id, "restored", item=row)
    db.commit()
    return service.data(row)


@router.post("/research-items/{rid}/favorite")
def favorite_item(
    rid: UUID,
    data: FavoriteInput | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(ResearchItem)
        .where(ResearchItem.id == rid, ResearchItem.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Research item not found")
    row.favorite = data.favorite if data is not None else not row.favorite
    service.audit(db, user.id, "favorite_changed", item=row)
    db.commit()
    return service.data(row)


@router.get("/research-items/{rid}/audit")
def item_audit(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    service.owned(db, ResearchItem, rid, user.id)
    return [
        service.data(row)
        for row in db.scalars(
            select(ResearchAudit)
            .where(ResearchAudit.item_id == rid, ResearchAudit.user_id == user.id)
            .order_by(ResearchAudit.created_at.desc())
            .limit(100)
        )
    ]


@router.post("/research-items/{rid}/extract-metadata")
def start_extraction(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return extraction.start(db, user, service.owned(db, ResearchItem, rid, user.id))


@router.get("/research-items/{rid}/extraction-status")
def extraction_status(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return extraction.status(db, user.id, service.owned(db, ResearchItem, rid, user.id))


@router.post("/research-items/{rid}/confirm-metadata")
def confirm_metadata(
    rid: UUID,
    data: MetadataReview,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return extraction.confirm(
        db, user, service.owned(db, ResearchItem, rid, user.id, lock=True), data
    )


@router.get("/research-tags")
def tags(
    q: str = Query("", max_length=80),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(ResearchTag).where(ResearchTag.user_id == user.id)
    if q:
        query = query.where(ResearchTag.name.ilike("%" + q + "%"))
    return [
        service.data(row)
        for row in db.scalars(
            query.order_by(ResearchTag.name).offset(offset).limit(limit)
        )
    ]


@router.post("/research-tags", status_code=201)
def create_tag(
    data: TagInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if not data.name.strip():
        raise HTTPException(422, "Tag name cannot be blank")
    row = service.tag_for(db, user.id, data.name)
    service.audit(
        db, user.id, "tag_saved", details={"tag_id": str(row.id), "name": row.name}
    )
    db.commit()
    return service.data(row)


@router.patch("/research-tags/{rid}")
def rename_tag(
    rid: UUID,
    data: TagInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = service.owned(db, ResearchTag, rid, user.id, lock=True)
    name = data.name.strip()
    if not name:
        raise HTTPException(422, "Tag name cannot be blank")
    old = row.name
    row.name = name
    row.normalized_name = name.casefold()
    try:
        for model, link, key in [
            (ResearchItem, ResearchItemTag, "item_id"),
            (ResearchNote, ResearchNoteTag, "note_id"),
        ]:
            records = db.scalars(
                select(model)
                .join(link, getattr(link, key) == model.id)
                .where(model.user_id == user.id, link.tag_id == rid)
            ).all()
            for record in records:
                record.tags = [
                    name if tag.casefold() == old.casefold() else tag
                    for tag in record.tags
                ]
        service.audit(
            db,
            user.id,
            "tag_renamed",
            details={"tag_id": str(rid), "previous_name": old, "name": name},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A tag with that name already exists")
    return service.data(row)


@router.delete("/research-tags/{rid}")
def delete_tag(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = service.owned(db, ResearchTag, rid, user.id, lock=True)
    if db.scalar(
        select(ResearchItemTag.item_id).where(ResearchItemTag.tag_id == rid).limit(1)
    ) or db.scalar(
        select(ResearchNoteTag.note_id).where(ResearchNoteTag.tag_id == rid).limit(1)
    ):
        raise HTTPException(
            409, "Remove this tag from items and notes before deleting it"
        )
    service.audit(
        db, user.id, "tag_deleted", details={"tag_id": str(rid), "name": row.name}
    )
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/research-notes")
def notes(
    q: str = Query("", max_length=500),
    case_id: UUID | None = None,
    item_id: UUID | None = None,
    tag: str | None = None,
    pinned: bool | None = None,
    archived: bool = False,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = select(ResearchNote).where(
        ResearchNote.user_id == user.id,
        ResearchNote.archived_at.is_not(None)
        if archived
        else ResearchNote.archived_at.is_(None),
    )
    if q:
        query = query.where(
            or_(
                *(
                    getattr(ResearchNote, key).ilike("%" + q + "%")
                    for key in ("title", "content", "quoted_text", "references")
                )
            )
        )
    if case_id:
        query = query.where(ResearchNote.case_id == case_id)
    if item_id:
        query = query.where(ResearchNote.item_id == item_id)
    if pinned is not None:
        query = query.where(ResearchNote.pinned == pinned)
    if tag:
        query = query.where(
            exists(
                select(ResearchNoteTag.note_id)
                .join(ResearchTag, ResearchTag.id == ResearchNoteTag.tag_id)
                .where(
                    ResearchNoteTag.note_id == ResearchNote.id,
                    ResearchTag.user_id == user.id,
                    ResearchTag.normalized_name == tag.strip().casefold(),
                )
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            service.data(row, brief=True)
            for row in db.scalars(
                query.order_by(
                    ResearchNote.pinned.desc(),
                    ResearchNote.updated_at.desc(),
                    ResearchNote.id,
                )
                .offset(offset)
                .limit(limit)
            )
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/research-notes", status_code=201)
def create_note(
    data: NoteInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    values = data.model_dump()
    service.validate_links(db, user.id, values)
    names = values.pop("tags")
    values["content"] = safe_html(values["content"])
    row = ResearchNote(user_id=user.id, **values)
    db.add(row)
    db.flush()
    service.set_tags(db, row, names)
    service.audit(db, user.id, "note_created", note=row)
    db.commit()
    return service.data(row)


@router.get("/research-notes/{rid}")
def note_detail(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return service.data(service.owned(db, ResearchNote, rid, user.id))


@router.patch("/research-notes/{rid}")
def update_note(
    rid: UUID,
    data: NotePatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    from pydantic import ValidationError

    row = service.owned(db, ResearchNote, rid, user.id, lock=True)
    try:
        values = NoteInput.model_validate(
            {
                **{key: getattr(row, key) for key in NoteInput.model_fields},
                **data.model_dump(exclude_unset=True),
            }
        ).model_dump()
    except ValidationError as error:
        raise HTTPException(422, error.errors()[0]["msg"])
    service.validate_links(db, user.id, values)
    names = values.pop("tags")
    values["content"] = safe_html(values["content"])
    for key, value in values.items():
        setattr(row, key, value)
    service.set_tags(db, row, names)
    service.audit(db, user.id, "note_edited", note=row)
    db.commit()
    return service.data(row)


@router.delete("/research-notes/{rid}")
def archive_note(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = service.owned(db, ResearchNote, rid, user.id)
    row.archived_at = service.now()
    service.audit(db, user.id, "note_archived", note=row)
    db.commit()
    return service.data(row)


@router.post("/research-notes/{rid}/restore")
def restore_note(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = service.owned(db, ResearchNote, rid, user.id)
    row.archived_at = None
    service.audit(db, user.id, "note_restored", note=row)
    db.commit()
    return service.data(row)


@router.get("/cases/{case_id}/research-items")
def case_items(
    case_id: UUID,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    service.owned(db, Case, case_id, user.id)
    return items(
        case_id=case_id,
        limit=limit,
        offset=offset,
        q="",
        item_type=None,
        court=None,
        from_date=None,
        to_date=None,
        language=None,
        tag=None,
        favorite=None,
        archived=False,
        sort="recent",
        user=user,
        db=db,
    )


@router.post("/cases/{case_id}/research-items")
def link_case(
    case_id: UUID,
    data: CaseLinkInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    service.owned(db, Case, case_id, user.id)
    item = service.owned(db, ResearchItem, data.item_id, user.id, lock=True)
    if not db.get(ResearchCaseLink, (item.id, case_id)):
        db.add(ResearchCaseLink(item_id=item.id, case_id=case_id))
    service.audit(
        db, user.id, "case_linked", item=item, details={"case_id": str(case_id)}
    )
    db.commit()
    return {"ok": True}


@router.delete("/cases/{case_id}/research-items/{rid}")
def unlink_case(
    case_id: UUID,
    rid: UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    service.owned(db, Case, case_id, user.id)
    item = service.owned(db, ResearchItem, rid, user.id)
    db.execute(
        delete(ResearchCaseLink).where(
            ResearchCaseLink.item_id == rid, ResearchCaseLink.case_id == case_id
        )
    )
    if item.case_id == case_id:
        item.case_id = None
    service.audit(
        db, user.id, "case_unlinked", item=item, details={"case_id": str(case_id)}
    )
    db.commit()
    return {"ok": True}

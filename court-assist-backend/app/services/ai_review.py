"""Explicit approval paths. AI workers have no access to these write operations."""

import html
from datetime import timezone

from fastapi import HTTPException
from lxml import html as dom

from app.api.v1.phase10 import snapshot
from app.models.drafting import DraftAudit
from app.models.phase10 import DraftDocument
from app.schemas.diary import DiaryCreate
from app.services import diary_service
from app.services.ai_context import owned
from app.services.draft_generation import safe_html


def require_result(job):
    if job.status != "completed" or job.result is None:
        raise HTTPException(409, "ai_result_not_ready")


def plain_to_html(text):
    return "<p>" + html.escape(text).replace("\n", "<br>") + "</p>"


def revision(stamp):
    if stamp.tzinfo:
        stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    return stamp.isoformat()


def replace_selection(content, selection, approved):
    root = dom.fragment_fromstring(safe_html(content), create_parent="div")
    hits = []
    for node in root.iter():
        for attr in ("text", "tail"):
            value = getattr(node, attr)
            if value:
                hits.extend((node, attr) for _ in range(value.count(selection)))
    if len(hits) != 1:
        raise HTTPException(409, "selection_no_longer_unique")
    node, attr = hits[0]
    setattr(node, attr, getattr(node, attr).replace(selection, approved, 1))
    wrapper = dom.tostring(root, encoding="unicode", method="html")
    return safe_html(wrapper[5:-6])


def approve_draft(db, user, job, data):
    require_result(job)
    if job.kind != "draft" or not job.draft_id:
        raise HTTPException(422, "not_a_draft_suggestion")
    if job.approval:
        return job.approval
    draft = owned(db, DraftDocument, user.id, job.draft_id, lock=True)
    if draft.archived_at:
        raise HTTPException(409, "draft_archived")
    if revision(draft.updated_at) != revision(data.expected_updated_at) or revision(draft.updated_at) != job.request_data["draft_revision"]:
        raise HTTPException(409, "draft_changed")
    if data.mode == "replace":
        content = replace_selection(draft.content, job.request_data["text"], data.text)
    else:
        content = safe_html(draft.content) + plain_to_html(data.text)
    if len(content) > 500000:
        raise HTTPException(422, "draft_too_large")
    snapshot(db, draft, "Before approved AI edit")
    draft.content = content
    db.add(DraftAudit(user_id=user.id, draft_id=draft.id, action="ai_suggestion_approved"))
    job.approval = {"draft_id": str(draft.id)}
    db.commit()
    return job.approval


def approve_diary(db, user, job, data):
    require_result(job)
    if job.kind not in ("diary", "dates", "chronology"):
        raise HTTPException(422, "not_a_diary_suggestion")
    if job.case_id and job.case_id != data.case_id:
        raise HTTPException(422, "case_does_not_match")
    if job.kind == "diary":
        if data.item_index is not None:
            raise HTTPException(422, "invalid_suggestion_index")
        key = "note"
    else:
        items = job.result["items"]
        if data.item_index is None or data.item_index >= len(items):
            raise HTTPException(422, "invalid_suggestion_index")
        key = str(data.item_index)
    previous = job.approval or {}
    if key in previous:
        return previous[key]
    # Create a separate private note. Keep the source diary entry and extracted evidence intact.
    entry = diary_service.create(db, user, DiaryCreate(
        case_id=data.case_id, entry_date=data.entry_date, title=data.title,
        entry_type="General Note", content=data.text, request_id=f"ai-{job.id}-{key}",
    ), commit=False)
    approved = {"diary_entry_id": str(entry.id)}
    job.approval = {**previous, key: approved}
    db.commit()
    return approved


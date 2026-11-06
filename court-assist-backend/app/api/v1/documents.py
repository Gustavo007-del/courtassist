import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.core.config import get_settings
from app.database.session import get_db
from app.models.case import Case
from app.models.client import Client
from app.models.hearing import Hearing
from app.models.court import Court
from app.models.document import Document, DocumentVersion, DocumentOCR, DocumentAccessLog
from app.models.user import User
from app.schemas.document import ConfirmUpload, DocumentCreate, DocumentOut, DocumentPatch, OCROut, SignedURL, VersionCreate, VersionOut
from app.services.document_storage import expires_at, finalize_object, presigned_get, presigned_put, storage_key, validate_file, verify_object
from app.services.document_ocr import queue_ocr, suggestions

router = APIRouter(tags=['documents'])


def owned(db: Session, model, record_id, user_id):
    record = db.get(model, record_id) if record_id else None
    if record_id and (not record or record.user_id != user_id):
        raise HTTPException(404, 'Linked record not found')
    return record


def links(db: Session, user_id, case_id, client_id, hearing_id):
    case = owned(db, Case, case_id, user_id)
    owned(db, Client, client_id, user_id)
    hearing = owned(db, Hearing, hearing_id, user_id)
    if hearing and case and hearing.case_id != case.id:
        raise HTTPException(422, 'Hearing belongs to another case')


def doc_or_404(db: Session, document_id, user_id):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user_id))
    if not doc:
        raise HTTPException(404, 'Document not found')
    return doc


def version_or_404(db: Session, doc: Document, version_id):
    version = db.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == doc.id, DocumentVersion.user_id == doc.user_id))
    if not version:
        raise HTTPException(404, 'Version not found')
    return version


def audit(db: Session, doc: Document, action: str):
    db.add(DocumentAccessLog(document_id=doc.id, user_id=doc.user_id, action=action))


@router.get('/documents/search')
def search_documents(q: str = Query(min_length=1, max_length=200), case_id: uuid.UUID | None = None,
                     client_id: uuid.UUID | None = None, court_id: uuid.UUID | None = None, category: str | None = None,
                     from_date: datetime | None = None, to_date: datetime | None = None,
                     exact: bool = False,
                     limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db), user: User = Depends(current_user)):
    term = f'%{q.strip()}%'
    ocr_expression = DocumentOCR.extracted_text.ilike(term)
    if db.bind and db.bind.dialect.name == 'postgresql':
        tsquery = func.phraseto_tsquery('simple', q.strip()) if exact else func.plainto_tsquery('simple', q.strip())
        ocr_expression = func.to_tsvector('simple', DocumentOCR.extracted_text).op('@@')(tsquery)
    ocr_match = exists(select(DocumentOCR.id).where(DocumentOCR.document_id == Document.id,
                    DocumentOCR.user_id == user.id, DocumentOCR.processing_status.in_(('completed', 'needs_review')),
                    ocr_expression))
    query = select(Document).outerjoin(Case, Case.id == Document.case_id).outerjoin(Client, Client.id == Document.client_id).where(Document.user_id == user.id, Document.is_archived.is_(False),
                                  or_(Document.document_name.ilike(term), Document.original_filename.ilike(term),
                                      Document.description.ilike(term), Document.document_category.ilike(term),
                                      Case.case_number.ilike(term), Case.cnr_number.ilike(term), Client.full_name.ilike(term), ocr_match))
    if case_id: query = query.where(Document.case_id == case_id)
    if client_id: query = query.where(Document.client_id == client_id)
    if court_id: query = query.where(Case.court_id == court_id)
    if category: query = query.where(Document.document_category == category)
    if from_date: query = query.where(Document.created_at >= from_date)
    if to_date: query = query.where(Document.created_at <= to_date)
    docs = db.scalars(query.order_by(Document.created_at.desc()).offset(offset).limit(limit)).all()
    items = []
    for item in docs:
        result = DocumentOut.model_validate(item).model_dump(mode='json')
        result['case_number'] = item.case_id and db.get(Case, item.case_id).case_number
        result['client_name'] = item.client_id and db.get(Client, item.client_id).full_name
        result['snippet'] = None; result['page_number'] = None
        ocr = db.scalar(select(DocumentOCR).where(DocumentOCR.document_id == item.id, DocumentOCR.user_id == user.id,
                        DocumentOCR.document_version_id == item.current_version_id))
        if ocr:
            for page in ocr.page_results:
                text = page.get('extracted_text') or ''
                at = text.lower().find(q.lower().strip())
                if at >= 0:
                    result['snippet'] = text[max(0, at - 50):at + len(q) + 100]
                    result['page_number'] = page.get('page_number')
                    break
        items.append(result)
    return {'items': items, 'limit': limit, 'offset': offset}


@router.get('/documents', response_model=list[DocumentOut])
def list_documents(case_id: uuid.UUID | None = None, client_id: uuid.UUID | None = None, hearing_id: uuid.UUID | None = None,
                   category: str | None = None, storage_status: str | None = None, mime_type: str | None = None,
                   ocr_status: str | None = None, from_date: datetime | None = None, to_date: datetime | None = None,
                   archived: bool = False,
                   limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Document).where(Document.user_id == user.id, Document.is_archived == archived)
    for field, value in ((Document.case_id, case_id), (Document.client_id, client_id), (Document.hearing_id, hearing_id), (Document.document_category, category), (Document.storage_status, storage_status), (Document.mime_type, mime_type)):
        if value is not None: query = query.where(field == value)
    if ocr_status: query = query.where(exists(select(DocumentOCR.id).where(DocumentOCR.document_id == Document.id, DocumentOCR.document_version_id == Document.current_version_id, DocumentOCR.processing_status == ocr_status)))
    if from_date: query = query.where(Document.created_at >= from_date)
    if to_date: query = query.where(Document.created_at <= to_date)
    return db.scalars(query.order_by(Document.created_at.desc()).offset(offset).limit(limit)).all()


@router.post('/documents', response_model=DocumentOut, status_code=201)
def create_document(data: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    safe_name, extension = validate_file(data.original_filename, data.mime_type, data.file_size)
    links(db, user.id, data.case_id, data.client_id, data.hearing_id)
    doc = Document(id=db.info.get("sync_record_id"), user_id=user.id, case_id=data.case_id, client_id=data.client_id, hearing_id=data.hearing_id,
                   document_name=data.document_name.strip(), original_filename=safe_name, file_extension=extension,
                   mime_type=data.mime_type, file_size=data.file_size, page_count=data.page_count,
                   document_category=data.document_category, description=data.description,
                   storage_status='upload_pending', checksum=data.checksum)
    db.add(doc); db.commit(); db.refresh(doc)
    return doc


@router.post('/documents/upload-url', response_model=SignedURL)
def upload_url(data: ConfirmUpload, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, data.document_id, user.id)
    if data.version_id:
        version = version_or_404(db, doc, data.version_id)
        if version.storage_status not in ('upload_pending', 'upload_failed', 'uploading'):
            raise HTTPException(409, 'Version is not awaiting upload')
    else:
        if doc.current_version_id:
            raise HTTPException(409, 'Create a new version to revise this document')
        version = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.version_number == 1))
        if not version:
            version = DocumentVersion(document_id=doc.id, user_id=user.id, version_number=1,
                                      storage_key=storage_key(user.id, doc.id, uuid.uuid4(), doc.file_extension),
                                      original_filename=doc.original_filename, file_size=doc.file_size,
                                      checksum=doc.checksum, change_description='Original upload')
            db.add(version); db.flush()
        elif version.storage_status not in ('upload_pending', 'upload_failed', 'uploading'):
            raise HTTPException(409, 'Original upload is already complete')
    url = presigned_put(version.storage_key, doc.mime_type)
    version.upload_expires_at = expires_at(); version.storage_status = 'uploading'
    if not doc.current_version_id: doc.storage_status = 'uploading'
    db.commit()
    return SignedURL(url=url, expires_in=get_settings().document_url_seconds, document_id=doc.id, version_id=version.id)


@router.post('/documents/confirm-upload', response_model=DocumentOut)
def confirm_upload(data: ConfirmUpload, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, data.document_id, user.id)
    version = version_or_404(db, doc, data.version_id) if data.version_id else db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.version_number == 1))
    if not version or version.storage_status != 'uploading':
        raise HTTPException(409, 'No active upload')
    expiry = version.upload_expires_at
    if not expiry or expiry.replace(tzinfo=expiry.tzinfo or timezone.utc) < datetime.now(timezone.utc):
        version.storage_status = 'upload_failed'
        if not doc.current_version_id: doc.storage_status = 'upload_failed'
        db.commit()
        raise HTTPException(410, 'Upload URL expired; request a new URL')
    try:
        checksum = verify_object(version.storage_key, doc.mime_type, version.file_size, version.checksum)
    except HTTPException:
        version.storage_status = 'upload_failed'
        if not doc.current_version_id: doc.storage_status = 'upload_failed'
        db.commit()
        raise
    final_key = storage_key(user.id, doc.id, version.id, doc.file_extension, stage='stored')
    finalize_object(version.storage_key, final_key, doc.mime_type, version.file_size, checksum)
    version.storage_key = final_key; version.checksum = checksum; version.storage_status = 'cloud_stored'; version.upload_expires_at = None
    doc.current_version_id = version.id; doc.storage_key = version.storage_key; doc.file_size = version.file_size
    doc.original_filename = version.original_filename; doc.checksum = checksum; doc.storage_status = 'cloud_stored'
    doc.uploaded_at = datetime.now(timezone.utc)
    audit(db, doc, 'upload_confirmed')
    if get_settings().ocr_provider != 'disabled':
        ocr = DocumentOCR(document_id=doc.id, user_id=user.id, document_version_id=version.id,
                          processing_provider=get_settings().ocr_provider, processing_status='pending')
        db.add(ocr)
    db.commit(); db.refresh(doc)
    if get_settings().ocr_provider != 'disabled':
        try:
            queue_ocr(str(ocr.id))
        except HTTPException:
            ocr.processing_status = 'failed'; ocr.error_message = 'OCR worker is unavailable'; db.commit()
    return doc


@router.get('/documents/{document_id}', response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return doc_or_404(db, document_id, user.id)


@router.patch('/documents/{document_id}', response_model=DocumentOut)
def patch_document(document_id: uuid.UUID, data: DocumentPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    changes = data.model_dump(exclude_unset=True)
    links(db, user.id, changes.get('case_id', doc.case_id), changes.get('client_id', doc.client_id), changes.get('hearing_id', doc.hearing_id))
    for key, value in changes.items(): setattr(doc, key, value)
    if doc.is_archived: doc.storage_status = 'archived'
    elif doc.storage_status == 'archived': doc.storage_status = 'cloud_stored' if doc.current_version_id else 'upload_pending'
    db.commit(); db.refresh(doc)
    return doc


@router.delete('/documents/{document_id}', status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    doc.is_archived = True; doc.storage_status = 'archived'; audit(db, doc, 'archived'); db.commit()


@router.get('/documents/{document_id}/download-url', response_model=SignedURL)
def download_url(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    if not doc.current_version_id: raise HTTPException(409, 'Document is not stored')
    version = version_or_404(db, doc, doc.current_version_id)
    if version.storage_status != 'cloud_stored': raise HTTPException(409, 'Document is not stored')
    url = presigned_get(version.storage_key, version.original_filename)
    audit(db, doc, 'download_url'); db.commit()
    return SignedURL(url=url, expires_in=get_settings().document_url_seconds, document_id=doc.id, version_id=version.id)


@router.get('/documents/{document_id}/versions', response_model=list[VersionOut])
def versions(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    return db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number.desc())).all()


@router.post('/documents/{document_id}/versions', response_model=VersionOut, status_code=201)
def create_version(document_id: uuid.UUID, data: VersionCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user.id).with_for_update())
    if not doc: raise HTTPException(404, 'Document not found')
    if not doc.current_version_id: raise HTTPException(409, 'Original upload is incomplete')
    safe_name, extension = validate_file(data.original_filename, doc.mime_type, data.file_size)
    if extension != doc.file_extension: raise HTTPException(422, 'Version file type must match the original')
    existing = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number.desc())).first()
    if existing and existing.storage_status != 'cloud_stored': raise HTTPException(409, 'Finish the pending version first')
    version = DocumentVersion(document_id=doc.id, user_id=user.id, version_number=existing.version_number + 1,
                              storage_key=storage_key(user.id, doc.id, uuid.uuid4(), extension), original_filename=safe_name,
                              file_size=data.file_size, checksum=data.checksum, change_description=data.change_description)
    db.add(version); db.commit(); db.refresh(version)
    return version


@router.get('/documents/{document_id}/versions/{version_id}', response_model=VersionOut)
def get_version(document_id: uuid.UUID, version_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return version_or_404(db, doc_or_404(db, document_id, user.id), version_id)


@router.get('/documents/{document_id}/versions/{version_id}/download-url', response_model=SignedURL)
def version_download_url(document_id: uuid.UUID, version_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id); version = version_or_404(db, doc, version_id)
    if version.storage_status != 'cloud_stored': raise HTTPException(409, 'Version is not stored')
    url = presigned_get(version.storage_key, version.original_filename)
    audit(db, doc, 'version_download_url'); db.commit()
    return SignedURL(url=url, expires_in=get_settings().document_url_seconds, document_id=doc.id, version_id=version.id)


@router.get('/cases/{case_id}/documents', response_model=list[DocumentOut])
def case_documents(case_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Case, case_id, user.id)
    return db.scalars(select(Document).where(Document.user_id == user.id, Document.case_id == case_id, Document.is_archived.is_(False)).order_by(Document.created_at.desc())).all()


@router.get('/clients/{client_id}/documents', response_model=list[DocumentOut])
def client_documents(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Client, client_id, user.id)
    return db.scalars(select(Document).where(Document.user_id == user.id, Document.client_id == client_id, Document.is_archived.is_(False)).order_by(Document.created_at.desc())).all()


@router.get('/hearings/{hearing_id}/documents', response_model=list[DocumentOut])
def hearing_documents(hearing_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned(db, Hearing, hearing_id, user.id)
    return db.scalars(select(Document).where(Document.user_id == user.id, Document.hearing_id == hearing_id, Document.is_archived.is_(False)).order_by(Document.created_at.desc())).all()


def latest_ocr(db: Session, doc: Document):
    if not doc.current_version_id:
        raise HTTPException(409, 'Document upload is incomplete')
    return db.scalar(select(DocumentOCR).where(DocumentOCR.document_id == doc.id,
                     DocumentOCR.document_version_id == doc.current_version_id, DocumentOCR.user_id == doc.user_id))


@router.post('/documents/{document_id}/ocr', response_model=OCROut)
def start_ocr(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    if doc.storage_status not in ('cloud_stored', 'archived') or not doc.current_version_id:
        raise HTTPException(409, 'Document upload is incomplete')
    record = latest_ocr(db, doc)
    if record and record.processing_status in ('pending', 'processing', 'completed', 'needs_review'):
        return record
    if not record:
        record = DocumentOCR(document_id=doc.id, user_id=user.id, document_version_id=doc.current_version_id,
                             processing_provider=get_settings().ocr_provider, processing_status='pending')
        db.add(record); db.flush()
    else:
        record.processing_status = 'pending'; record.error_message = None
    db.commit(); db.refresh(record)
    try: queue_ocr(str(record.id))
    except HTTPException:
        record.processing_status = 'failed'; record.error_message = 'OCR worker is unavailable'; db.commit()
        raise
    return record


@router.post('/documents/{document_id}/ocr/retry', response_model=OCROut)
def retry_ocr(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    record = latest_ocr(db, doc)
    if not record or record.processing_status not in ('failed', 'needs_review'):
        raise HTTPException(409, 'No failed OCR job to retry')
    record.processing_status = 'pending'; record.error_message = None
    db.commit(); db.refresh(record)
    try: queue_ocr(str(record.id))
    except HTTPException:
        record.processing_status = 'failed'; record.error_message = 'OCR worker is unavailable'; db.commit()
        raise
    return record


@router.get('/documents/{document_id}/ocr-status')
def ocr_status(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    record = latest_ocr(db, doc_or_404(db, document_id, user.id))
    return {'processing_status': record.processing_status if record else 'not_started'}


@router.get('/documents/{document_id}/ocr', response_model=OCROut)
def get_ocr(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    record = latest_ocr(db, doc_or_404(db, document_id, user.id))
    if not record: raise HTTPException(404, 'OCR result not found')
    return record


@router.get('/documents/{document_id}/extracted-metadata')
def extracted_metadata(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    record = latest_ocr(db, doc_or_404(db, document_id, user.id))
    if not record or record.processing_status not in ('completed', 'needs_review'):
        raise HTTPException(409, 'OCR result is not available')
    return {'suggestions': suggestions(record.page_results), 'reviewed': doc_or_404(db, document_id, user.id).reviewed_metadata}


@router.post('/documents/{document_id}/extracted-metadata/confirm')
def confirm_metadata(document_id: uuid.UUID, choices: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    doc = doc_or_404(db, document_id, user.id)
    record = latest_ocr(db, doc)
    if not record or record.processing_status not in ('completed', 'needs_review'):
        raise HTTPException(409, 'OCR result is not available')
    reviewed = choices.get('reviewed', [])
    if not isinstance(reviewed, list): raise HTTPException(422, 'Invalid review')
    available = {(item['field'], item['value']) for item in suggestions(record.page_results)}
    valid_status = {'accepted', 'edited', 'rejected'}
    for item in reviewed:
        if not isinstance(item, dict) or (item.get('field'), item.get('source_value')) not in available or item.get('status') not in valid_status:
            raise HTTPException(422, 'Suggestion is unavailable')
        if item['status'] != 'rejected' and (not isinstance(item.get('value'), str) or not item['value'].strip() or len(item['value']) > 240):
            raise HTTPException(422, 'Reviewed value is invalid')
    doc.reviewed_metadata = reviewed
    audit(db, doc, 'metadata_reviewed'); db.commit()
    return {'reviewed': reviewed, 'note': 'Review recorded; case details were not changed'}

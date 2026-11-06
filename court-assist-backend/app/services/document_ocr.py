import io
import logging
import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.document import Document, DocumentVersion, DocumentOCR
from app.models.user import User
from app.services.document_storage import client


def extract_pages(content: bytes, mime_type: str, provider: str):
    if mime_type in ('text/plain','application/vnd.openxmlformats-officedocument.wordprocessingml.document'):
        if mime_type=='text/plain':text=content.decode('utf-8-sig')
        else:
            from docx import Document as WordDocument
            document=WordDocument(io.BytesIO(content))
            paragraphs=[]
            for node in document.element.body:
                kind=node.tag.rsplit('}',1)[-1]
                candidates=[node] if kind=='p' else node.xpath('.//w:p') if kind=='tbl' else []
                paragraphs.extend(''.join(part.text or '' for part in paragraph.xpath('.//w:t')) for paragraph in candidates)
            text='\n'.join(paragraphs)
        return [{'page_number':None,'page_reference':'Unpaginated source text','extracted_text':text,'language':None,'confidence_score':None,'processing_status':'completed','bounding_boxes':[]}]
    if mime_type == 'application/pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        if len(reader.pages) > 500:
            raise RuntimeError('Document has too many pages for OCR')
        pages = []
        rendered = None
        try:
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ''
                if not text.strip() and provider == 'tesseract':
                    import fitz
                    import pytesseract
                    from PIL import Image
                    if rendered is None: rendered = fitz.open(stream=content, filetype='pdf')
                    rendered_page = rendered.load_page(number - 1)
                    if rendered_page.rect.get_area() * (150 / 72) ** 2 > 16_000_000:
                        raise RuntimeError('PDF page exceeds rendering budget')
                    pixmap = rendered_page.get_pixmap(dpi=150)
                    text = pytesseract.image_to_string(Image.open(io.BytesIO(pixmap.tobytes('png'))), lang='eng+mal', timeout=20)
                pages.append({'page_number': number, 'extracted_text': text, 'language': None,
                              'confidence_score': None, 'processing_status': 'completed', 'bounding_boxes': []})
        finally:
            if rendered is not None: rendered.close()
        return pages
    if provider == 'tesseract' and mime_type in ('image/jpeg', 'image/png'):
        from PIL import Image
        import pytesseract
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > 16_000_000:
                raise RuntimeError('Image exceeds rendering budget')
            text = pytesseract.image_to_string(image, lang='eng+mal', timeout=20)
        return [{'page_number': 1, 'extracted_text': text, 'language': None,
                 'confidence_score': None, 'processing_status': 'completed', 'bounding_boxes': []}]
    raise RuntimeError('No OCR provider configured for this file type')


def suggestions(page_results: list):
    patterns = {
        'cnr_number': r'\b[A-Z]{4}\d{12}\b',
        'case_number': r'\b(?:[A-Z]{1,8}[. ]*\s*\d+\s*[/.-]\s*\d{4})\b',
        'document_date': r'\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b',
        'filing_date': r'\b(?:filing|filed)\s+date\s*[:\-]\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})',
        'order_date': r'\b(?:order|judgment)\s+date\s*[:\-]\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})',
        'court_name': r'\b(?:in the\s+)?(?:hon.?ble\s+)?(?:high|district|family|sessions|munsiff|magistrate)\s+court[^\n]{0,100}',
        'petitioner': r'\bpetitioner\s*[:\-]\s*([^\n]{2,100})',
        'respondent': r'\brespondent\s*[:\-]\s*([^\n]{2,100})',
        'advocate_name': r'\badvocate\s*[:\-]\s*([^\n]{2,100})',
        'document_type': r'\b(?:Petition|Judgment|Affidavit|Vakalath|Legal Notice|Court Order)\b',
        'case_title': r'(?im)^\s*case\s+(?:title|name)\s*[:\-]\s*([^\n]{2,240})',
        'citation': r'(?im)^\s*(?:neutral\s+)?citation\s*[:\-]\s*([^\n]{2,240})',
        'act_name': r'(?im)^\s*(?:act|statute)\s*[:\-]\s*([^\n]{2,240})',
        'section_number': r'(?im)^\s*(?:section|sections|rule|rules)\s*[:\-]\s*([^\n]{1,240})',
    }
    found = []
    for page in page_results:
        text = page.get('extracted_text') or ''
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = (match.group(1) if match.lastindex else match.group(0)).strip()
                found.append({'field': field, 'value': value, 'source_text': match.group(0),
                              'page_number': page['page_number'], 'confidence': None})
    return found


def process_ocr(ocr_id: str):
    with SessionLocal() as db:
        try:identifier=uuid.UUID(str(ocr_id))
        except ValueError:return
        record = db.scalar(select(DocumentOCR).where(DocumentOCR.id==identifier).with_for_update())
        if not record or record.processing_status not in ('pending', 'failed'):
            return
        record.processing_status = 'processing'; db.commit()
        try:
            if not db.scalar(select(User.is_active).where(User.id == record.user_id)):
                raise RuntimeError('Account is unavailable')
            doc = db.get(Document, record.document_id)
            version = db.get(DocumentVersion, record.document_version_id)
            if not doc or not version or doc.user_id!=record.user_id or version.user_id!=record.user_id or version.document_id!=doc.id or version.storage_status not in ('cloud_stored','stored'):
                raise RuntimeError('Stored document version is unavailable')
            settings = get_settings()
            response = client().get_object(Bucket=settings.document_s3_bucket, Key=version.storage_key)
            try:content = response['Body'].read(settings.document_max_bytes + 1)
            finally:response['Body'].close()
            if len(content) > settings.document_max_bytes:
                raise RuntimeError('Document exceeds configured size limit')
            pages = extract_pages(content, doc.mime_type, settings.ocr_provider)
            record.page_results = pages
            record.extracted_text = '\n'.join(page['extracted_text'] for page in pages)
            record.processing_status = 'completed' if record.extracted_text.strip() else 'needs_review'
            record.language_detected = None
            record.error_message = None
            record.processed_at = datetime.now(timezone.utc)
        except Exception:
            logging.getLogger(__name__).warning('document_ocr_failed')
            record.processing_status = 'failed'
            record.error_message = 'Text extraction failed; retry or review the file'
        db.commit()


def queue_ocr(ocr_id: str):
    settings = get_settings()
    if not settings.redis_url or settings.ocr_provider == 'disabled':
        raise HTTPException(503, 'OCR worker is not configured')
    from celery import Celery
    app = Celery('court_assist_ocr', broker=settings.redis_url)
    try:
        app.send_task('app.workers.ocr.process_document_ocr', args=[ocr_id], queue='court-assist-ocr')
    except Exception:
        raise HTTPException(503, 'OCR worker is unavailable')

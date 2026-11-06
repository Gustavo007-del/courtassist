import hashlib
import uuid
import io
import zipfile
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from urllib.parse import quote, urlparse
from fastapi import HTTPException
from app.core.config import get_settings
from app.schemas.document import TYPES
from app.services.malware_scan import scan_upload


def safe_filename(value: str):
    return re.sub(r'[\x00-\x1f\x7f]', '_', PurePath(value.replace('\\', '/')).name)


def validate_file(filename: str, mime_type: str, size: int):
    settings = get_settings()
    if size <= 0 or size > settings.document_max_bytes:
        raise HTTPException(422, 'Document size is outside the allowed range')
    safe_name = safe_filename(filename)
    extension = '.' + safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if extension not in TYPES or TYPES[extension] != mime_type:
        raise HTTPException(422, 'Unsupported document type')
    return safe_name, extension


def storage_key(user_id: uuid.UUID, document_id: uuid.UUID, version_id: uuid.UUID, extension: str, stage: str = 'staging'):
    if stage not in ('staging', 'stored'):
        raise ValueError('Invalid storage stage')
    return f'documents/{stage}/{user_id}/{document_id}/{version_id}/{uuid.uuid4().hex}{extension}'


def client():
    settings = get_settings()
    if not all((settings.document_s3_bucket, settings.document_s3_access_key, settings.document_s3_secret_key)):
        raise HTTPException(503, 'Private document storage is not configured')
    if settings.document_s3_endpoint:
        endpoint = urlparse(settings.document_s3_endpoint)
        if endpoint.scheme != 'https' and not (settings.app_env == 'development' and endpoint.hostname in ('localhost', '127.0.0.1')):
            raise HTTPException(503, 'Private storage requires HTTPS')
    import boto3
    from botocore.config import Config
    return boto3.client('s3', endpoint_url=settings.document_s3_endpoint or None,
                        region_name=settings.document_s3_region,
                        aws_access_key_id=settings.document_s3_access_key,
                        aws_secret_access_key=settings.document_s3_secret_key,
                        config=Config(signature_version='s3v4', connect_timeout=3, read_timeout=15,
                                      retries={'total_max_attempts': 2},
                                      s3={'addressing_style': 'path'} if settings.document_s3_endpoint else {}))


def presigned_put(key: str, mime_type: str):
    settings = get_settings()
    return client().generate_presigned_url('put_object', Params={'Bucket': settings.document_s3_bucket, 'Key': key, 'ContentType': mime_type}, ExpiresIn=settings.document_url_seconds)


def presigned_get(key: str, filename: str):
    settings = get_settings()
    safe_name = quote(safe_filename(filename), safe='')
    return client().generate_presigned_url('get_object', Params={'Bucket': settings.document_s3_bucket, 'Key': key, 'ResponseContentDisposition': f"attachment; filename*=UTF-8''{safe_name}"}, ExpiresIn=settings.document_url_seconds)


def verify_object(key: str, mime_type: str, expected_size: int, expected_checksum: str | None):
    settings = get_settings()
    s3 = client()
    try:
        head = s3.head_object(Bucket=settings.document_s3_bucket, Key=key)
        if head['ContentLength'] != expected_size or head['ContentLength'] > settings.document_max_bytes:
            raise HTTPException(422, 'Uploaded document size does not match')
        response = s3.get_object(Bucket=settings.document_s3_bucket, Key=key)
        stream = response['Body']
        digest = hashlib.sha256()
        prefix = b''
        count = 0
        archive = bytearray() if mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' else None
        text_content=bytearray() if mime_type=='text/plain' else None
        with scan_upload(key.startswith('documents/staging/')) as scanner:
            while chunk := stream.read(1024 * 1024):
                count += len(chunk)
                if count > settings.document_max_bytes:
                    raise HTTPException(422, 'Document exceeds the size limit')
                if len(prefix) < 16:
                    prefix += chunk[:16 - len(prefix)]
                digest.update(chunk)
                if scanner is not None:
                    scanner.send(chunk)
                if archive is not None:archive.extend(chunk)
                if text_content is not None:text_content.extend(chunk)
            if scanner is not None:
                scanner.finish()
        if count != expected_size:
            raise HTTPException(422, 'Uploaded document size does not match')
        if mime_type == 'application/pdf' and not prefix.startswith(b'%PDF-'):
            raise HTTPException(422, 'Invalid PDF signature')
        if mime_type == 'image/jpeg' and not prefix.startswith(b'\xff\xd8\xff'):
            raise HTTPException(422, 'Invalid JPEG signature')
        if mime_type == 'image/png' and not prefix.startswith(b'\x89PNG\r\n\x1a\n'):
            raise HTTPException(422, 'Invalid PNG signature')
        if archive is not None:
            try:
                with zipfile.ZipFile(io.BytesIO(archive)) as office:
                    names=office.namelist()
                    if '[Content_Types].xml' not in names or 'word/document.xml' not in names or len(names)>2000 or sum(item.file_size for item in office.infolist())>100*1024*1024 or any('vbaproject' in name.lower() for name in names):
                        raise HTTPException(422,'Invalid or unsupported DOCX structure')
            except zipfile.BadZipFile:raise HTTPException(422,'Invalid DOCX signature')
        if text_content is not None:
            try:plain=text_content.decode('utf-8-sig')
            except UnicodeDecodeError:raise HTTPException(422,'Text files must use UTF-8 encoding')
            if any(ord(character)<32 and character not in '\n\r\t\f' for character in plain):raise HTTPException(422,'Binary content is not permitted in a text file')
        actual = digest.hexdigest()
        if expected_checksum and actual.lower() != expected_checksum.lower():
            raise HTTPException(422, 'Document checksum does not match')
        return actual
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(409, 'Upload is unavailable or incomplete')
    finally:
        try:
            stream.close()
        except (NameError, UnboundLocalError):
            pass


def expires_at():
    return datetime.now(timezone.utc) + timedelta(seconds=get_settings().document_url_seconds)


def finalize_object(staging_key: str, final_key: str, mime_type: str, size: int, checksum: str):
    settings = get_settings()
    s3 = client()
    try:
        s3.copy_object(Bucket=settings.document_s3_bucket, Key=final_key,
                       CopySource={'Bucket': settings.document_s3_bucket, 'Key': staging_key})
        verify_object(final_key, mime_type, size, checksum)
        s3.delete_object(Bucket=settings.document_s3_bucket, Key=staging_key)
    except Exception:
        try: s3.delete_object(Bucket=settings.document_s3_bucket, Key=final_key)
        except Exception: pass
        raise HTTPException(409, 'Could not finalize the private upload')

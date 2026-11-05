import os
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.config import get_settings
from app.models.image_upload import ImageUpload
from app.models.user import User
from app.schemas.image import ImageUploadUrl
from app.services.activity_service import record_activity

MAX_IMAGE_BYTES = 5 * 1024 * 1024
EXTENSIONS = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}


class PrivateImageStorage:
    def __init__(self):
        self.root = Path(get_settings().private_storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def temporary(self, upload_id: uuid.UUID) -> Path:
        folder = self.root / 'pending'
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f'{upload_id}.part'

    def key(self, user_id: uuid.UUID, upload_id: uuid.UUID, content_type: str) -> str:
        return f'{user_id}/{upload_id}{EXTENSIONS[content_type]}'

    def file(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise HTTPException(400, 'Invalid image key')
        return path


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _signature_valid(content_type: str, first_bytes: bytes) -> bool:
    if content_type == 'image/jpeg':
        return first_bytes.startswith(b'\xff\xd8\xff')
    if content_type == 'image/png':
        return first_bytes.startswith(b'\x89PNG\r\n\x1a\n')
    return first_bytes.startswith(b'RIFF') and first_bytes[8:12] == b'WEBP'


def _sanitize_image(path: Path, content_type: str) -> None:
    expected = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}[content_type]
    cleaned = path.with_suffix('.clean')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as source:
                if source.format != expected or getattr(source, 'n_frames', 1) != 1 or source.width * source.height > 16_000_000:
                    raise HTTPException(415, 'Unsupported image content')
                output = ImageOps.exif_transpose(source)
                if expected == 'JPEG':
                    output = output.convert('RGB')
                    output.save(cleaned, format='JPEG', quality=85, optimize=True)
                elif expected == 'PNG':
                    output.save(cleaned, format='PNG', optimize=True)
                else:
                    output.save(cleaned, format='WEBP', quality=85)
        if cleaned.stat().st_size > MAX_IMAGE_BYTES:
            raise HTTPException(413, 'Image exceeds 5 MB')
        os.replace(cleaned, path)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise HTTPException(415, 'Invalid image content') from exc
    finally:
        cleaned.unlink(missing_ok=True)


def create_upload(db: Session, user: User, purpose: str, content_type: str) -> ImageUploadUrl:
    upload = ImageUpload(user_id=user.id, purpose=purpose, content_type=content_type,
                         status='pending', expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    db.add(upload)
    db.commit()
    return ImageUploadUrl(upload_id=upload.id,
                          upload_url=f'/api/v1/users/me/{purpose}-image/uploads/{upload.id}',
                          expires_at=upload.expires_at)


async def receive_upload(db: Session, user: User, purpose: str, upload_id: uuid.UUID, request: Request) -> None:
    upload = db.scalar(select(ImageUpload).where(ImageUpload.id == upload_id, ImageUpload.user_id == user.id).with_for_update())
    if not upload or upload.purpose != purpose or upload.status != 'pending' or _aware(upload.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(404, 'Upload unavailable')
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != upload.content_type:
        raise HTTPException(415, 'Image type does not match upload request')
    storage = PrivateImageStorage()
    destination = storage.temporary(upload_id)
    size = 0
    try:
        with destination.open('wb') as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise HTTPException(413, 'Image exceeds 5 MB')
                output.write(chunk)
        with destination.open('rb') as source:
            first_bytes = source.read(12)
        if size == 0 or not _signature_valid(upload.content_type, first_bytes):
            raise HTTPException(415, 'Invalid image content')
        _sanitize_image(destination, upload.content_type)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    upload.status = 'uploaded'
    db.commit()


def confirm_upload(db: Session, user: User, purpose: str, upload_id: uuid.UUID) -> User:
    upload = db.scalar(select(ImageUpload).where(ImageUpload.id == upload_id, ImageUpload.user_id == user.id).with_for_update())
    if not upload or upload.purpose != purpose or upload.status != 'uploaded' or _aware(upload.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(404, 'Upload unavailable')
    storage = PrivateImageStorage()
    temporary = storage.temporary(upload_id)
    if not temporary.is_file():
        raise HTTPException(404, 'Image data unavailable')
    key = storage.key(user.id, upload_id, upload.content_type)
    final = storage.file(key)
    final.parent.mkdir(parents=True, exist_ok=True)
    old_key = user.profile_image if purpose == 'profile' else user.signature_image
    os.replace(temporary, final)
    if purpose == 'profile':
        user.profile_image = key
    else:
        user.signature_image = key
    upload.status = 'confirmed'
    record_activity(db, user.id, f'{purpose}_image_updated', f'{purpose.title()} image updated',
                    entity_type='user', entity_id=user.id)
    db.commit()
    db.refresh(user)
    if old_key:
        storage.file(old_key).unlink(missing_ok=True)
    return user


def image_file(user: User, purpose: str) -> Path:
    key = user.profile_image if purpose == 'profile' else user.signature_image
    if not key:
        raise HTTPException(404, 'Image unavailable')
    path = PrivateImageStorage().file(key)
    if not path.is_file():
        raise HTTPException(404, 'Image unavailable')
    return path

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel


class ImageUploadRequest(BaseModel):
    content_type: Literal['image/jpeg', 'image/png', 'image/webp']


class ImageUploadUrl(BaseModel):
    upload_id: UUID
    upload_url: str
    expires_at: datetime
    method: str = 'PUT'


class ImageConfirm(BaseModel):
    upload_id: UUID

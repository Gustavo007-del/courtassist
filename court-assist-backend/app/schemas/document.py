from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

CATEGORIES = {'Petition', 'Counter Affidavit', 'Written Statement', 'Judgment', 'Court Order', 'Vakalath', 'Evidence', 'Witness Documents', 'Legal Notice', 'Application', 'Affidavit', 'Case Records', 'Identity Documents', 'Medical Records', 'Agreements', 'Receipts', 'Invoices', 'Other'}
TYPES = {'.pdf': 'application/pdf', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.txt': 'text/plain', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}


class DocumentCreate(BaseModel):
    document_name: str = Field(min_length=1, max_length=240)
    original_filename: str = Field(min_length=1, max_length=240)
    mime_type: str
    file_size: int = Field(gt=0)
    page_count: int | None = Field(default=None, ge=1)
    document_category: str = 'Other'
    description: str = Field(default='', max_length=5000)
    case_id: UUID | None = None
    client_id: UUID | None = None
    hearing_id: UUID | None = None
    checksum: str | None = Field(default=None, pattern=r'^[a-fA-F0-9]{64}$')

    @field_validator('document_category')
    @classmethod
    def category_valid(cls, value):
        if value not in CATEGORIES:
            raise ValueError('Unsupported document category')
        return value


class DocumentPatch(BaseModel):
    document_name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    document_category: str | None = None
    case_id: UUID | None = None
    client_id: UUID | None = None
    hearing_id: UUID | None = None
    is_archived: bool | None = None

    @field_validator('document_category')
    @classmethod
    def category_valid(cls, value):
        if value is not None and value not in CATEGORIES:
            raise ValueError('Unsupported document category')
        return value


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    case_id: UUID | None
    client_id: UUID | None
    hearing_id: UUID | None
    document_name: str
    original_filename: str
    file_extension: str
    mime_type: str
    file_size: int
    page_count: int | None
    document_category: str
    description: str
    reviewed_metadata: list
    storage_provider: str
    storage_status: str
    checksum: str | None
    is_archived: bool
    current_version_id: UUID | None
    uploaded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VersionCreate(BaseModel):
    original_filename: str = Field(min_length=1, max_length=240)
    file_size: int = Field(gt=0)
    checksum: str | None = Field(default=None, pattern=r'^[a-fA-F0-9]{64}$')
    change_description: str = Field(default='', max_length=500)


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    user_id: UUID
    version_number: int
    original_filename: str
    file_size: int
    checksum: str | None
    change_description: str
    storage_status: str
    created_at: datetime


class ConfirmUpload(BaseModel):
    document_id: UUID
    version_id: UUID | None = None


class SignedURL(BaseModel):
    url: str
    expires_in: int
    document_id: UUID
    version_id: UUID


class OCROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    document_version_id: UUID
    processing_status: str
    processing_provider: str
    extracted_text: str
    language_detected: str | None
    page_results: list
    error_message: str | None
    processed_at: datetime | None

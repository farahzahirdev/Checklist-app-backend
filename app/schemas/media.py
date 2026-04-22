from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.media import MediaType, MalwareScanStatus


class MediaBase(BaseModel):
    filename: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    media_type: MediaType


class MediaUploadResponse(MediaBase):
    id: UUID
    sha256: str
    scan_status: MalwareScanStatus
    encryption_status: str
    created_at: datetime


class MediaResponse(MediaBase):
    id: UUID
    sha256: str
    scan_status: MalwareScanStatus
    encryption_status: str
    uploaded_by: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

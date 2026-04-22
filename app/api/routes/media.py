import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.media import Media, MediaType
from app.models.user import UserRole
from app.schemas.media import MediaResponse, MediaUploadResponse

router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png", 
    "image/gif",
    "image/webp",
    "application/pdf"
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

UPLOAD_DIR = Path("uploads/media")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Media File",
    description="Upload a media file (image or document) for use in checklist questions and answer options.",
)
def upload_media(
    file: UploadFile,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> MediaUploadResponse:
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES} bytes"
        )
    
    # Generate unique filename
    file_extension = Path(file.filename).suffix if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file"
        )
    
    # Determine media type
    if file.content_type.startswith("image/"):
        media_type = MediaType.image
    else:
        media_type = MediaType.document
    
    # Create media record
    media = Media(
        filename=unique_filename,
        original_filename=file.filename or "unknown",
        mime_type=file.content_type,
        file_size_bytes=file_size,
        file_path=str(file_path),
        media_type=media_type,
    )
    
    db.add(media)
    db.commit()
    db.refresh(media)
    
    return MediaUploadResponse(
        id=media.id,
        filename=media.filename,
        original_filename=media.original_filename,
        mime_type=media.mime_type,
        file_size_bytes=media.file_size_bytes,
        media_type=media.media_type,
        created_at=media.created_at,
    )


@router.get(
    "/{media_id}",
    response_model=MediaResponse,
    summary="Get Media Info",
    description="Retrieve information about a specific media file.",
)
def get_media(
    media_id: uuid.UUID,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> MediaResponse:
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    return MediaResponse(
        id=media.id,
        filename=media.filename,
        original_filename=media.original_filename,
        mime_type=media.mime_type,
        file_size_bytes=media.file_size_bytes,
        media_type=media.media_type,
        is_active=media.is_active,
        created_at=media.created_at,
        updated_at=media.updated_at,
    )


@router.get(
    "/{media_id}/download",
    summary="Download Media File",
    description="Download the actual media file.",
)
def download_media(
    media_id: uuid.UUID,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    if not media.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media is not active"
        )
    
    file_path = Path(media.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )
    
    from fastapi.responses import FileResponse
    
    return FileResponse(
        path=file_path,
        filename=media.original_filename,
        media_type=media.mime_type,
    )

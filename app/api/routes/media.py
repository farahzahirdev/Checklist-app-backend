import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models.media import Media, MediaType, MalwareScanStatus
from app.models.user import UserRole
from app.schemas.media import MediaResponse, MediaUploadResponse
from app.utils.file_upload import compute_sha256, basic_malware_scan

router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png", 
    "image/gif",
    "image/webp",
    "application/pdf"
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

def get_upload_dir() -> Path:
    """Get upload directory, creating it if needed."""
    settings = get_settings()
    upload_dir = Path(settings.upload_dir or "uploads/media")
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback to temporary directory if upload dir is not writable
        import tempfile
        upload_dir = Path(tempfile.gettempdir()) / "checklist_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


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
    
    # Generate unique filename for S3
    file_extension = Path(file.filename).suffix if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    # Read file content for scanning and hashing
    content = file.file.read()
    file.file.seek(0)

    # Perform malware scan
    if not basic_malware_scan(file.file):
        scan_status = MalwareScanStatus.infected
    else:
        scan_status = MalwareScanStatus.clean

    # Compute SHA256 hash
    sha256_hash = compute_sha256(file.file)
    file.file.seek(0)

    # Upload file to S3
    from app.utils.s3_upload import upload_file_to_s3
    try:
        s3_key = upload_file_to_s3(file, unique_filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {str(e)}"
        )
    
    # Determine media type
    if file.content_type.startswith("image/"):
        media_type = MediaType.image
    else:
        media_type = MediaType.document
    
    # Create media record (admin media is NOT encrypted)
    media = Media(
        filename=unique_filename,
        original_filename=file.filename or "unknown",
        mime_type=file.content_type,
        file_size_bytes=file_size,
        file_path=s3_key,  # Store S3 key instead of local path
        media_type=media_type,
        sha256=sha256_hash,
        scan_status=scan_status,
        encryption_status="unencrypted",  # Admin media is not encrypted
        uploaded_by=admin.id,
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
        sha256=media.sha256,
        scan_status=media.scan_status,
        encryption_status=media.encryption_status,
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
    
    # Handle both file path and base64 storage
    if media.file_path.startswith("base64:"):
        # File stored as base64 (serverless fallback)
        from fastapi.responses import Response
        import base64
        
        # In a real implementation, we'd retrieve the base64 data from database
        # For now, return an error message
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File download not available in serverless environment. Please contact admin."
        )
    else:
        # Regular file path
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


@router.get(
    "/{media_id}/preview",
    summary="Preview Media File",
    description="Preview a media file (publicly accessible for illustrative images in assessments).",
)
def preview_media(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Public endpoint for previewing media files used in assessments."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Media preview requested for ID: {media_id}")
    
    media = db.get(Media, media_id)
    if media is None:
        logger.warning(f"Media not found in database: {media_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    logger.info(f"Media found: {media.filename}, type: {media.media_type}, active: {media.is_active}, scan: {media.scan_status}")
    
    # Only allow preview of active media that are images and clean
    if not media.is_active:
        logger.warning(f"Media is not active: {media_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media is not active"
        )
    
    if media.media_type != MediaType.image:
        logger.warning(f"Media is not an image: {media_id}, type: {media.media_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preview is only available for image files"
        )
    
    if media.scan_status != MalwareScanStatus.clean:
        logger.warning(f"Media scan status not clean: {media_id}, status: {media.scan_status}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Media cannot be previewed due to scan status"
        )
    
    # Check if file is stored in S3 or locally
    settings = get_settings()
    s3_key = media.file_path
    
    logger.info(f"Checking media storage: S3 key = {s3_key}")
    
    # Try to serve from S3 first (most common case)
    if s3_key and not s3_key.startswith('/'):
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
            from fastapi.responses import Response
            
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_default_region,
            )
            
            bucket_arn = settings.s3_bucket_arn
            logger.info(f"Fetching file from S3: bucket={bucket_arn}, key={s3_key}")
            
            s3_object = s3_client.get_object(Bucket=bucket_arn, Key=s3_key)
            file_content = s3_object['Body'].read()
            
            logger.info(f"Successfully fetched file from S3, size: {len(file_content)} bytes")
            
            return Response(
                content=file_content,
                media_type=media.mime_type,
                headers={
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "Content-Disposition": "inline",  # Show inline instead of download
                    "Content-Length": str(len(file_content)),
                }
            )
            
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to fetch file from S3: {str(e)}")
            # Fall through to local file check as backup
        except Exception as e:
            logger.error(f"Unexpected error fetching from S3: {str(e)}")
            # Fall through to local file check as backup
    
    # Check if file exists locally (fallback for local storage or development)
    file_path = Path(media.file_path)
    logger.info(f"Checking local file path: {file_path}")
    
    if file_path.exists():
        try:
            from fastapi.responses import FileResponse
            
            logger.info(f"Returning local file response for: {file_path}")
            return FileResponse(
                path=file_path,
                filename=media.original_filename,
                media_type=media.mime_type,
                # Add cache headers for better performance
                headers={
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "Content-Disposition": "inline",  # Show inline instead of download
                }
            )
        except Exception as e:
            logger.error(f"Error serving local file {file_path}: {str(e)}")
    
    # If we get here, the file couldn't be found anywhere
    logger.error(f"File not found in S3 or locally for media: {media_id}")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Preview not available - media file not found in S3 or on disk. The media exists in the database but the actual file is missing."
    )


@router.get(
    "/{media_id}/debug",
    summary="Debug Media Info",
    description="Debug endpoint to check media details and file status (admin only).",
)
def debug_media(
    media_id: uuid.UUID,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Admin debug endpoint to investigate media issues."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Debug media requested for ID: {media_id}")
    
    media = db.get(Media, media_id)
    if media is None:
        return {
            "media_id": str(media_id),
            "found": False,
            "error": "Media not found in database"
        }
    
    # Check file existence
    file_path = Path(media.file_path)
    file_exists = file_path.exists()
    
    # Get file info if exists
    file_info = None
    if file_exists:
        try:
            stat = file_path.stat()
            file_info = {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "readable": os.access(file_path, os.R_OK)
            }
        except Exception as e:
            file_info = {"error": str(e)}
    
    return {
        "media_id": str(media_id),
        "found": True,
        "database_info": {
            "filename": media.filename,
            "original_filename": media.original_filename,
            "mime_type": media.mime_type,
            "media_type": media.media_type.value,
            "file_size_bytes": media.file_size_bytes,
            "file_path": media.file_path,
            "scan_status": media.scan_status.value,
            "encryption_status": media.encryption_status,
            "is_active": media.is_active,
            "created_at": media.created_at.isoformat() if media.created_at else None,
            "uploaded_by": str(media.uploaded_by)
        },
        "file_status": {
            "exists": file_exists,
            "path": str(file_path),
            "info": file_info
        }
    }

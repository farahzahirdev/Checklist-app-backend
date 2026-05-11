import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile, HTTPException, status
from app.core.config import get_settings
import uuid
import os


async def validate_upload_file(file: UploadFile, max_file_size_mb: int = 10) -> None:
    """
    Validate an uploaded file for size and MIME type.
    Raises ValueError if validation fails.
    """
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to start
    
    max_size_bytes = max_file_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        raise ValueError(f"File size exceeds maximum of {max_file_size_mb}MB")
    
    # Check MIME type
    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'}
    if file.content_type not in allowed_types:
        raise ValueError(f"File type {file.content_type} not allowed. Allowed types: {', '.join(allowed_types)}")


async def upload_to_s3(file: UploadFile) -> tuple[str, int]:
    """
    Upload a file to AWS S3 and return (file_path, file_size).
    """
    settings = get_settings()
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename or "file")[1]
    unique_filename = f"cms-images/{uuid.uuid4()}{file_ext}"
    
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )
    
    # Get file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to start
    
    # Extract bucket name from ARN
    bucket_arn = settings.s3_bucket_arn
    try:
        s3_client.upload_fileobj(
            file.file,
            bucket_arn,
            unique_filename,
        )
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {str(e)}"
        )
    
    return unique_filename, file_size


def upload_file_to_s3(file: UploadFile, unique_filename: str) -> str:
    """
    Uploads a file to AWS S3 and returns the S3 object key.
    """
    settings = get_settings()
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )
    # Extract bucket name from ARN (for access point, use ARN directly)
    bucket_arn = settings.s3_bucket_arn
    try:
        s3_client.upload_fileobj(
            file.file,
            bucket_arn,
            unique_filename,
        )
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {str(e)}"
        )
    return unique_filename

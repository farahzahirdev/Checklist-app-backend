import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile, HTTPException, status
from app.core.config import get_settings
import uuid


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

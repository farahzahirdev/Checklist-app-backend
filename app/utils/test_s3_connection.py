import boto3
from botocore.exceptions import BotoCoreError, ClientError
from app.core.config import get_settings

def test_s3_connection():
    settings = get_settings()
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_default_region,
    )
    bucket_arn = settings.s3_bucket_arn
    try:
        # Try to list objects in the bucket/access point
        response = s3_client.list_objects_v2(Bucket=bucket_arn, MaxKeys=1)
        print("S3 connection successful! Response:", response)
        return True
    except (BotoCoreError, ClientError) as e:
        print("S3 connection failed:", e)
        return False

if __name__ == "__main__":
    test_s3_connection()

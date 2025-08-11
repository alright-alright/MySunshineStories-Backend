import boto3
import os
from botocore.exceptions import BotoCoreError, ClientError
from typing import Optional

class S3Service:
    def __init__(self):
        self.s3_client = None
        if all([
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
            os.getenv("AWS_REGION"),
            os.getenv("AWS_S3_BUCKET")
        ]):
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION")
            )
    
    def upload_pdf(self, file_path: str, key: str) -> Optional[str]:
        """Upload PDF to S3 and return public URL"""
        if not self.s3_client:
            print("S3 not configured, skipping upload")
            return None
            
        bucket = os.getenv("AWS_S3_BUCKET")
        
        try:
            with open(file_path, 'rb') as file:
                self.s3_client.upload_fileobj(
                    file,
                    bucket,
                    key,
                    ExtraArgs={
                        'ContentType': 'application/pdf',
                        'ACL': 'public-read'
                    }
                )
            
            return f"https://{bucket}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{key}"
            
        except (BotoCoreError, ClientError) as e:
            print(f"Error uploading to S3: {e}")
            return None

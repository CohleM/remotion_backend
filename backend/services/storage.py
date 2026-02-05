# backend/services/storage.py
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException, UploadFile
import uuid
import os
from typing import Optional

from backend.config import settings

class R2Storage:
    def __init__(self):
        self.client = boto3.client(
            service_name="s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto"
        )
        self.bucket_name = settings.R2_BUCKET_NAME
    
    def _generate_unique_filename(self, original_filename: str, user_id: int) -> str:
        """Generate unique filename with user prefix"""
        extension = original_filename.split('.')[-1].lower()
        unique_id = str(uuid.uuid4())[:8]
        return f"user_{user_id}/{unique_id}_{original_filename}"
    
    async def upload_file(
        self, 
        file: UploadFile, 
        user_id: int,
        folder: str = "uploads"
    ) -> dict:
        """
        Upload file to R2 storage
        Returns: dict with file_url, file_key, size, content_type
        """
        # Validate file type
        allowed_types = [
            'video/mp4', 'video/webm', 'video/quicktime',
            'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg',
            'audio/x-m4a', 'video/x-matroska'
        ]
        
        content_type = file.content_type or 'application/octet-stream'
        
        if not any(content_type.startswith(t.split('/')[0]) for t in allowed_types):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type: {content_type}. Only video and audio files allowed."
            )
        
        # Generate unique key
        file_key = f"{folder}/{self._generate_unique_filename(file.filename, user_id)}"
        
        try:
            # Read file content
            content = await file.read()
            file_size = len(content)
            
            # Check file size (e.g., 500MB limit)
            max_size = 500 * 1024 * 1024  # 500MB
            if file_size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max size is 500MB"
                )
            
            # Upload to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    'original-filename': file.filename,
                    'uploaded-by': str(user_id)
                }
            )
            
            # Generate URL
            if settings.R2_PUBLIC_URL:
                file_url = f"{settings.R2_PUBLIC_URL}/{file_key}"
            else:
                # Generate presigned URL for private buckets
                file_url = self.client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': file_key},
                    ExpiresIn=3600 * 24 * 30  # 30 days
                )
            
            await file.close()
            
            return {
                "file_key": file_key,
                "file_url": file_url,
                "original_name": file.filename,
                "size": file_size,
                "content_type": content_type
            }
            
        except NoCredentialsError:
            raise HTTPException(status_code=500, detail="R2 credentials not available")
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    def delete_file(self, file_key: str) -> bool:
        """Delete file from R2"""
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
        except ClientError:
            return False
    
    def get_file_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Get presigned URL for file access"""
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")

# Singleton instance
storage = R2Storage()
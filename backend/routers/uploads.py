# backend/routers/uploads.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import uuid
import mimetypes

from backend import crud, schemas
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.config import settings
from botocore.config import Config

router = APIRouter(prefix="/uploads", tags=["uploads"])



# Initialize R2 client
# s3_client = boto3.client(
#     service_name="s3",
#     endpoint_url=settings.R2_ENDPOINT_URL,
#     aws_access_key_id=settings.R2_ACCESS_KEY_ID,
#     aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
#     region_name="auto"
# )

s3_client = boto3.client(
    service_name='s3',
    endpoint_url=settings.R2_ENDPOINT_URL,
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(
        read_timeout=900,
        connect_timeout=60,
        retries={'max_attempts': 3, 'mode': 'adaptive'}
    ),
    region_name="auto"
)


ALLOWED_TYPES = {
    'video/mp4', 'video/webm', 'video/quicktime', 'video/mov',
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/x-m4a'
}

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

def get_content_type(filename: str, declared_type: Optional[str]) -> str:
    """Determine content type from filename or declared type"""
    if declared_type and declared_type != 'application/octet-stream':
        return declared_type
    
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or 'application/octet-stream'

def generate_video_key(user_id: int, filename: str) -> str:
    """Generate unique R2 key for video"""
    ext = filename.split('.')[-1].lower() if '.' in filename else 'mp4'
    unique_id = str(uuid.uuid4())[:12]
    return f"videos/user_{user_id}/{unique_id}.{ext}"

@router.post("/video", response_model=schemas.VideoUploadResponse)
async def upload_video_direct(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Direct upload from frontend → R2 → Database → Return video_id
    Streams file directly to R2 without saving locally
    """

    print('file name', file.filename, 'name', name) 
    # Validate content type
    content_type = get_content_type(file.filename, file.content_type)
    
    if not any(content_type.startswith(t) for t in ['video/', 'audio/']):
        # Check extension as fallback
        ext = file.filename.split('.')[-1].lower()
        if ext not in ['mp4', 'mov', 'webm', 'mp3', 'wav', 'm4a', 'ogg']:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {content_type}. Only video/audio allowed."
            )
        # Force content type for known extensions
        if ext in ['mp4', 'mov', 'webm']:
            content_type = f"video/{ext if ext != 'mov' else 'quicktime'}"
        else:
            content_type = f"audio/{ext}"
    
    # Generate unique key
    file_key = generate_video_key(current_user.id, file.filename)
    
    # Stream upload to R2
    try:
        # Use multipart upload for large files
        upload_id = s3_client.create_multipart_upload(
            Bucket=settings.R2_BUCKET_NAME,
            Key=file_key,
            ContentType=content_type,
            Metadata={
                'original-filename': file.filename,
                'uploaded-by': str(current_user.id),
                'content-type': content_type
            }
        )['UploadId']
        
        parts = []
        part_number = 1
        total_size = 0
        
        # Stream in chunks (8MB chunks)
        chunk_size = 8 * 1024 * 1024
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            
            total_size += len(chunk)
            
            if total_size > MAX_FILE_SIZE:
                # Abort multipart upload
                s3_client.abort_multipart_upload(
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=file_key,
                    UploadId=upload_id
                )
                raise HTTPException(status_code=400, detail="File too large (max 2GB)")
            
            # Upload part
            response = s3_client.upload_part(
                Bucket=settings.R2_BUCKET_NAME,
                Key=file_key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=chunk
            )
            
            parts.append({
                'PartNumber': part_number,
                'ETag': response['ETag']
            })
            part_number += 1
        
        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=settings.R2_BUCKET_NAME,
            Key=file_key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )
        
        # Generate URL (presigned or public)
        if settings.R2_PUBLIC_URL:
            file_url = f"{settings.R2_PUBLIC_URL}/{file_key}"
        else:
            file_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.R2_BUCKET_NAME, 'Key': file_key},
                ExpiresIn=7*24*3600  # 7 days
            )
        
        # Create video record in database
        video = crud.create_video_with_upload(
            db=db,
            user_id=current_user.id,
            original_filename=file.filename,
            content_type=content_type,
            file_size=total_size,
            original_url=file_url,
            name=name,
            duration=None  # Could extract with ffprobe in background
        )
        
        # Optional: Trigger background processing (transcoding, thumbnail, etc.)
        # background_tasks.add_task(process_video, video.id, file_key)
        
        return schemas.VideoUploadResponse(
            video_id=video.id,
            status=video.status,
            message="Video uploaded successfully",
            original_url=file_url,
            name=name,
            user_id=current_user.id
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"R2 upload failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()

@router.get("/video/{video_id}/status")
def get_upload_status(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Check video processing status"""
    video = crud.get_video(db, video_id)
    if not video or video.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return {
        "video_id": video.id,
        "status": video.status,
        "original_url": video.original_url,
        "high_res_url": video.high_res_url,
        "progress": None  # Could add processing progress here
    }
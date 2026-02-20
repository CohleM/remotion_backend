from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from botocore.exceptions import ReadTimeoutError
from backend import crud, schemas
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.services.storage import storage  # For getting fresh URLs


from backend.routers.uploads import s3_client  # Import from uploads.py
from backend.config import settings
from subtitle_generator.async_llm_client import get_transcript_async
from subtitle_generator.transcript_modification import apply_styles
import os
import tempfile
import asyncio
import math

from subtitle_generator.utils.video_modification import convert_mp4_to_mp3, convert_video_lowres, get_video_info

router = APIRouter(prefix="/videos", tags=["videos"])

@router.get("/", response_model=List[schemas.VideoResponseWithoutTranscript])
def get_my_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Get all videos for current user"""
    videos = crud.get_videos_by_user(db, current_user.id, skip=skip, limit=limit)
    return videos

@router.get("/{video_id}", response_model=schemas.VideoResponse)
def get_video(
    video_id: int,
    fresh_url: bool = False,  # Option to get fresh presigned URL
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Get video details.
    Set fresh_url=true to get a new presigned URL if using private bucket
    """
    video = crud.get_video(db, video_id)
    if not video or video.owner_id != current_user.id:
        # return {"message": "Video not found", "video_id": video_id}
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Optionally refresh the URL if it's expired
    if fresh_url and not settings.R2_PUBLIC_URL:
        # Extract key from URL or store key separately
        # For now, regenerate based on known pattern or stored key
        pass
    
    return video

@router.put("/{video_id}", response_model=schemas.VideoResponse)
def update_video(
    video_id: int,
    video_update: schemas.VideoUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Update video metadata (name, transcript, style, etc.)"""
    video = crud.get_video(db, video_id)
    if not video or video.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Don't allow URL updates through this endpoint
    update_data = video_update.model_dump(exclude_unset=True)
    for field in ['original_url', 'low_res_url', 'high_res_url', 'content_type', 'file_size']:
        update_data.pop(field, None)
    
    for field, value in update_data.items():
        setattr(video, field, value)
    
    db.commit()
    db.refresh(video)
    return video

@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Delete video and associated R2 files"""
    video = crud.get_video(db, video_id)
    if not video or video.owner_id != current_user.id:
        return {"message": "Video not found", "video_id": video_id}
        # raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete from R2 if needed (optional - could keep files)
    # storage.delete_file(extract_key_from_url(video.original_url))
    
    # Delete from database
    crud.delete_video(db, video_id)
    
    return {"message": "Video deleted", "video_id": video_id}




def get_video_key_from_url(video_url: str) -> str:
    """Extract R2 key from presigned URL or public URL"""
    if settings.R2_PUBLIC_URL and settings.R2_PUBLIC_URL in video_url:
        return video_url.replace(f"{settings.R2_PUBLIC_URL}/", "")
    
    if "?" in video_url:
        base_url = video_url.split("?")[0]
        parts = base_url.split("/")
        try:
            videos_index = parts.index("videos")
            return "/".join(parts[videos_index:])
        except ValueError:
            pass
    
    raise HTTPException(status_code=400, detail="Could not extract file key from URL")


async def upload_lowres_to_r2(local_path: str, user_id: str, video_id: str) -> str:
    """
    Upload low-res video to R2 and return the URL.
    Runs in thread pool to not block event loop.
    """
    def _upload():
        filename = os.path.basename(local_path)
        file_key = f"videos/user_{user_id}/lowres/{video_id}_{filename}"
        
        with open(local_path, 'rb') as f:
            s3_client.put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=file_key,
                Body=f,
                ContentType='video/mp4'
            )
        
        if settings.R2_PUBLIC_URL:
            return f"{settings.R2_PUBLIC_URL}/{file_key}"
        else:
            return s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.R2_BUCKET_NAME, 'Key': file_key},
                ExpiresIn=7*24*3600
            )
    
    # Run sync boto3 in thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _upload)


async def process_video_async(
    local_file_path: str,
    user_id: str,
    video_id: str
) -> tuple[dict, str]:
    """
    Process video: create low-res, extract audio, get transcript, upload low-res.
    Returns: (transcript_data, low_res_url)
    """
    # Step 1: Convert to low-res (CPU intensive - run in thread)
    loop = asyncio.get_event_loop()
    lowres_path = await loop.run_in_executor(
        None, 
        convert_video_lowres, 
        local_file_path
    )
    print(f"Low-res created: {lowres_path}")
    
    # Step 2: Extract audio (CPU intensive - run in thread)
    audio_path = await loop.run_in_executor(
        None,
        convert_mp4_to_mp3,
        lowres_path
    )
    print(f"Audio extracted: {audio_path}")
    
    # Step 3: Run transcription and R2 upload concurrently
    transcript_task = asyncio.create_task(get_transcript_async(audio_path))
    upload_task = asyncio.create_task(
        upload_lowres_to_r2(lowres_path, user_id, video_id)
    )
    
    # Wait for both to complete
    transcript, low_res_url = await asyncio.gather(transcript_task, upload_task)
    
    print(f"Transcript received: {len(str(transcript))} chars")
    print(f"Low-res uploaded: {low_res_url}")
    
    return transcript, low_res_url, lowres_path, audio_path

# backend/routers/videos.py

@router.post("/generate")
async def generate_captions(
    request: schemas.GenerateCaptionsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    # Validate video exists and belongs to user
    video = crud.get_video(db, int(request.video_id))
    if not video or video.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")

    # Mark as queued immediately
    crud.update_video(db, int(request.video_id), schemas.VideoUpdate(
        status="processing",
        progress=0,
        current_step="queued"
    ))

    # Fire and return
    background_tasks.add_task(run_generation_pipeline, request)

    return {
        "video_id": request.video_id,
        "status": "processing"
    }


@router.get("/generate/status/{video_id}")
def get_generation_status(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    video = crud.get_video(db, video_id)
    if not video or video.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "video_id": video.id,
        "status": video.status,           # processing | ready | error
        "progress": video.progress,        # 0-100
        "current_step": video.current_step # "downloading" | "transcribing" etc.
    }



@router.post("/change_styles")
async def change_styles(
    request: schemas.ChangeStyleRequest,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Change or generate new styles for an existing video.
    If style exists in all_styles_mapping, switch to it.
    If not, generate new style, save it, and switch to it.
    """
    
    print("=" * 60)
    print("STARTING STYLE CHANGE PIPELINE")
    print("=" * 60)
    
    print(f"\n[REQUEST] User: {current_user.id}, Video: {request.video_id}")
    print(f"[REQUEST] Style Config ID: {request.style_config.get('id', 'default')}")
    
    # Get video from database
    video = crud.get_video(db, int(request.video_id))
    if not video or video.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if video has transcript
    if not video.transcript:
        raise HTTPException(status_code=400, detail="Video has no transcript. Generate captions first.")
    
    style_id = request.style_config.get('id', 'default')
    
    # Check if style already exists in all_styles_mapping
    existing_styles = video.all_styles_mapping or {}
    
    if style_id in existing_styles:
        # Style exists - just switch to it
        print(f"\n[STYLE EXISTS] Switching to existing style '{style_id}' (ID: {existing_styles[style_id]})")
        
        # Update video to use this style
        video_update = schemas.VideoUpdate(
            current_style=request.style_config,
            style_id=existing_styles[style_id]
        )
        updated_video = crud.update_video(db, int(request.video_id), video_update)
        
        # Get the style result for response
        style = crud.get_style(db, existing_styles[style_id])
        
        print(f"[SUCCESS] Switched to existing style '{style_id}'")
        
        return {
            "success": True,
            "video_id": request.video_id,
            "style_id": existing_styles[style_id],
            "style_name": style_id,
            "current_style": request.style_config,
            "result": style.styled_transcript if style else None,
            "message": f"Switched to existing style '{style_id}'",
            "is_new_style": False
        }
    
    else:
        # Style doesn't exist - generate it
        print(f"\n[NEW STYLE] Generating new style '{style_id}'...")
        
        try:
            # Get transcript from video (already a dict/JSON)
            transcript_json = video.transcript
            if isinstance(transcript_json, str):
                import json
                transcript_json = json.loads(transcript_json)
            
            # Generate new style
            print(f"[GENERATING] Applying style '{style_id}' to transcript...")
            result = await apply_styles(transcript_json, style_id)
            print(f"[GENERATED] Style result: {len(str(result))} chars")
            
            # Create new style in database
            style_data = {
                "name": style_id,
                "description": f"Generated captions for video {request.video_id}",
                "styled_transcript": result
            }
            
            new_style = schemas.StyleCreate(**style_data)
            style = crud.create_style(db, new_style, creator_id=current_user.id)
            print(f"[DATABASE] Created new style with id: {style.id}")
            
            # Update all_styles_mapping with new style
            updated_styles_mapping = {**existing_styles, style_id: style.id}
            
            # Update video with new style
            video_update = schemas.VideoUpdate(
                current_style=request.style_config,
                style_id=style.id,
                all_styles_mapping=updated_styles_mapping
            )
            updated_video = crud.update_video(db, int(request.video_id), video_update)
            print(f"[DATABASE] Updated video with new style mapping")
            
            print("\n" + "=" * 60)
            print("STYLE CHANGE COMPLETE - NEW STYLE CREATED")
            print("=" * 60)
            
            return {
                "success": True,
                "video_id": request.video_id,
                "style_id": style.id,
                "style_name": style_id,
                "current_style": request.style_config,
                "result": result,
                "message": f"Generated and switched to new style '{style_id}'",
                "is_new_style": True,
                "all_styles": list(updated_styles_mapping.keys())
            }
            
        except Exception as e:
            print(f"\n[ERROR] Style generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            raise HTTPException(
                status_code=500, 
                detail=f"Style generation failed: {str(e)}"
            )



##########################################################################################
# Render Job

@router.post("/render")
def create_render_job(
    video_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import uuid
    from backend.models import RenderJob

    video = crud.get_video(db, video_id)
    style = crud.get_style(db, video.style_id)

    job = RenderJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        video_id=video_id,
        input_props={
            "transcript": style.styled_transcript,
            "customStyleConfigs": video.current_style,
            "videoUrl": video.high_res_url,
            "videoInfo": {
                "width": math.floor(video.width),
                "height": math.floor(video.height),
                "fps": math.floor(video.fps),
                "durationInFrames": math.floor(video.duration * video.fps)
            },
            "captionPadding": video.caption_padding,
            "style" : video.current_style['id']
        }
    )

    db.add(job)
    db.commit()

    # ✅ Save job id to video
    video_update = schemas.VideoUpdate(
        render_job_id=str(job.id)
    )
    crud.update_video(db, video_id, video_update)

    return {"jobId": str(job.id)}


@router.get("/render/{job_id}")
def get_render_status(job_id: str, db: Session = Depends(get_db)):
    job = crud.get_render_job(db, job_id)

    if not job:
        raise HTTPException(404)

    signed_url = None

    if job.status == "completed" and job.output_url:
        signed_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': settings.R2_BUCKET_NAME, 'Key': job.output_url, 'ResponseContentDisposition': 'attachment; filename="video.mp4"'},
                        ExpiresIn=1*3600,
                        
                    )

    return {
        "status": job.status,
        "progress": job.progress,
        "videoUrl": signed_url or "",
        "videoId" : job.video_id
    }



async def run_generation_pipeline(request: schemas.GenerateCaptionsRequest):
    from backend.database import SessionLocal
    db = SessionLocal()

    temp_dir = os.path.join(tempfile.gettempdir(), f"{request.user_id}-{request.video_id}")
    os.makedirs(temp_dir, exist_ok=True)
    local_file_path = os.path.join(temp_dir, request.video_filename)
    lowres_path = None
    audio_path = None

    def update_progress(progress: int, step: str):
        """Single helper — updates the video row directly"""
        crud.update_video(db, int(request.video_id), schemas.VideoUpdate(
            progress=progress,
            current_step=step
        ))
        print(f"[video {request.video_id}] {progress}% — {step}")

    try:
        # ── Stage 1: downloading ─────────────────────────────────────
        

        # file_key = get_video_key_from_url(request.video_url)
        # response = s3_client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=file_key)
        # with open(local_file_path, 'wb') as f:
        #     for chunk in response['Body'].iter_chunks(chunk_size=8192):
        #         f.write(chunk)

        update_progress(5, "downloading")
        file_key = get_video_key_from_url(request.video_url)
        await download_video_from_r2(file_key, local_file_path, int(request.video_id), db)

        # ── Stage 2: converting to low-res ───────────────────────────
        update_progress(20, "converting")
        loop = asyncio.get_event_loop()
        width, height, duration_in_seconds, fps = get_video_info(local_file_path)
        lowres_path = await loop.run_in_executor(None, convert_video_lowres, local_file_path)

        # ── Stage 3: extracting audio ────────────────────────────────
        update_progress(40, "extracting_audio")
        audio_path = await loop.run_in_executor(None, convert_mp4_to_mp3, lowres_path)

        # ── Stage 4: transcribing + uploading lowres concurrently ────
        update_progress(55, "transcribing")
        transcript, low_res_url = await asyncio.gather(
            asyncio.create_task(get_transcript_async(audio_path)),
            asyncio.create_task(upload_lowres_to_r2(lowres_path, request.user_id, request.video_id))
        )

        # ── Stage 5: applying styles ─────────────────────────────────
        update_progress(85, "applying_styles")
        style_name = request.style_config.get('id', 'default')
        result = await apply_styles(transcript, style_name)

        style = crud.create_style(
            db,
            schemas.StyleCreate(
                name=style_name,
                description=f"Generated captions for video {request.video_id}",
                styled_transcript=result
            ),
            creator_id=int(request.user_id)
        )

        caption_padding = int(height - (1/3)*height)

        # ── Stage 6: final update — all fields at once ───────────────
        crud.update_video(db, int(request.video_id), schemas.VideoUpdate(
            transcript=transcript,
            low_res_url=low_res_url,
            status="ready",
            progress=100,
            current_step="completed",
            current_style=request.style_config,
            width=width,
            height=height,
            fps=fps,
            duration=duration_in_seconds,
            style_id=style.id,
            all_styles_mapping={style_name: style.id},
            caption_padding=caption_padding

        ))

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Write error back to the video row
        crud.update_video(db, int(request.video_id), schemas.VideoUpdate(
            status="error",
            current_step=f"failed: {str(e)}"
        ))

    finally:
        for path in [local_file_path, lowres_path, audio_path]:
            if path:
                try:
                    os.remove(path)
                except:
                    pass
        db.close()


@router.post("/{video_id}/caption-padding")
def update_caption_padding(
    video_id: int,
    padding_update: schemas.CaptionPaddingUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Update only the caption padding for a video (auto-save endpoint)
    """
    video = crud.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Only allow update if user owns this video
    if video.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this video")
    
    updated_video = crud.update_caption_padding(db, video_id, padding_update.caption_padding)
    return updated_video




# Enhanced download function
async def download_video_from_r2(
    file_key: str, 
    local_path: str, 
    video_id: int,
    db,
    max_retries: int = 3
):
    """
    Download video from R2 with:
    - Retry logic
    - Progress updates
    - Larger chunk size
    - Timeout handling
    """
    loop = asyncio.get_event_loop()
    
    for attempt in range(max_retries):
        try:
            def _download():
                response = s3_client.get_object(
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=file_key
                )
                
                file_size = response.get('ContentLength', 0)
                downloaded = 0
                
                with open(local_path, 'wb') as f:
                    for chunk in response['Body'].iter_chunks(chunk_size=131072):  # 128KB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update every 10% of download
                        if file_size > 0:
                            progress = int((downloaded / file_size) * 15)
                            if downloaded % (file_size // 10) < 131072:
                                crud.update_video(db, video_id, schemas.VideoUpdate(
                                    progress=5 + progress,
                                    current_step=f"downloading"
                                ))
            
            await loop.run_in_executor(None, _download)
            return  # Success
            
        except ReadTimeoutError as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"Download timeout, retry {attempt + 2}/{max_retries} in {wait_time}s...")
                crud.update_video(db, video_id, schemas.VideoUpdate(
                    current_step=f"download retry {attempt + 2}/{max_retries}"
                ))
                await asyncio.sleep(wait_time)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to download video after {max_retries} attempts"
                )
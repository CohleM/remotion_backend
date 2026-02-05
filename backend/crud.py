# backend/crud.py
from sqlalchemy.orm import Session
from backend import models, schemas
from typing import Optional, List

# ============== User CRUD ==============

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_google_id(db: Session, google_id: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.google_id == google_id).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        email=user.email,
        google_id=user.google_id,
        name=user.name,
        picture=user.picture,
        credits=50  # Give initial free credits
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_credits(db: Session, user_id: int, credits: int) -> models.User:
    user = get_user(db, user_id)
    if user:
        user.credits = credits
        db.commit()
        db.refresh(user)
    return user

def add_credits(db: Session, user_id: int, amount: int) -> models.User:
    user = get_user(db, user_id)
    if user:
        user.credits += amount
        db.commit()
        db.refresh(user)
    return user


# ============== Video CRUD ==============

def get_video(db: Session, video_id: int) -> Optional[models.Video]:
    return db.query(models.Video).filter(models.Video.id == video_id).first()

def get_videos_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Video]:
    return db.query(models.Video).filter(models.Video.owner_id == user_id).offset(skip).limit(limit).all()

def create_video(db: Session, video: schemas.VideoCreate, user_id: int) -> models.Video:
    db_video = models.Video(
        name=video.name,
        transcript=video.transcript,
        owner_id=user_id,
        current_style={}
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

def update_video(db: Session, video_id: int, video_update: schemas.VideoUpdate) -> Optional[models.Video]:
    video = get_video(db, video_id)
    if not video:
        return None
    
    update_data = video_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(video, field, value)
    
    db.commit()
    db.refresh(video)
    return video

def delete_video(db: Session, video_id: int) -> bool:
    video = get_video(db, video_id)
    if video:
        db.delete(video)
        db.commit()
        return True
    return False


# ============== Style CRUD ==============

def get_style(db: Session, style_id: int) -> Optional[models.Style]:
    return db.query(models.Style).filter(models.Style.id == style_id).first()

def get_styles(db: Session, skip: int = 0, limit: int = 100, include_default: bool = True) -> List[models.Style]:
    query = db.query(models.Style)
    if not include_default:
        query = query.filter(models.Style.is_default == 0)
    return query.offset(skip).limit(limit).all()

def get_default_styles(db: Session) -> List[models.Style]:
    return db.query(models.Style).filter(models.Style.is_default == 1).all()

def create_style(db: Session, style: schemas.StyleCreate, creator_id: Optional[int] = None) -> models.Style:
    db_style = models.Style(
        name=style.name,
        description=style.description,
        three_lines=style.three_lines,
        two_lines=style.two_lines,
        one_line=style.one_line,
        spotlight=style.spotlight,
        split_screen=style.split_screen,
        minimal=style.minimal,
        dynamic=style.dynamic,
        creator_id=creator_id,
        is_default=0 if creator_id else 1
    )
    db.add(db_style)
    db.commit()
    db.refresh(db_style)
    return db_style

def update_style(db: Session, style_id: int, style_update: schemas.StyleUpdate) -> Optional[models.Style]:
    style = get_style(db, style_id)
    if not style:
        return None
    
    update_data = style_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(style, field, value)
    
    db.commit()
    db.refresh(style)
    return style

def delete_style(db: Session, style_id: int) -> bool:
    style = get_style(db, style_id)
    if style and style.is_default == 0:  # Only delete non-default styles
        db.delete(style)
        db.commit()
        return True
    return False


    # backend/crud.py
def create_video_with_upload(
    db: Session, 
    user_id: int,
    original_filename: str,
    content_type: str,
    file_size: int,
    original_url: str,
    name: Optional[str] = None,
    duration: Optional[int] = None
) -> models.Video:
    db_video = models.Video(
        name=name or original_filename,
        original_filename=original_filename,
        content_type=content_type,
        file_size=file_size,
        original_url=original_url,
        high_res_url=original_url,
        status="uploaded",
        duration=duration,
        owner_id=user_id,
        current_style={}
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

def update_video_status(db: Session, video_id: int, status: str, 
                       low_res_url: Optional[str] = None,
                       high_res_url: Optional[str] = None) -> Optional[models.Video]:
    """Update processing status and URLs after transcoding"""
    video = get_video(db, video_id)
    if video:
        video.status = status
        if low_res_url:
            video.low_res_url = low_res_url
        if high_res_url:
            video.high_res_url = high_res_url
        db.commit()
        db.refresh(video)
    return video

# Remove or simplify old create_video function
def create_video(db: Session, video: schemas.VideoCreate, user_id: int) -> models.Video:
    """Legacy create - use create_video_with_upload instead"""
    db_video = models.Video(
        name=video.name,
        owner_id=user_id,
        current_style={},
        status="created"
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

def update_video(db: Session, video_id: int, video_update: schemas.VideoUpdate) -> Optional[models.Video]:
    video = get_video(db, video_id)
    if not video:
        return None
    
    update_data = video_update.model_dump(exclude_unset=True)
    
    # Handle transcript JSON serialization if using Text column
    # If using JSON column in model, SQLAlchemy handles it automatically
    if 'transcript' in update_data and update_data['transcript'] is not None:
        # If your DB column is Text not JSON, uncomment:
        # update_data['transcript'] = json.dumps(update_data['transcript'])
        pass
    
    for field, value in update_data.items():
        setattr(video, field, value)
    
    db.commit()
    db.refresh(video)
    return video 
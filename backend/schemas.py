# backend/schemas.py
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

# ============== User Schemas ==============

class UserBase(BaseModel):
    email: str 
    name: Optional[str] = None
    picture: Optional[str] = None

class UserCreate(UserBase):
    google_id: str


# ============== Style Schemas ==============

class StyleBase(BaseModel):
    name: str
    description: Optional[str] = None

class StyleCreate(StyleBase):
    three_lines: Optional[Dict[str, Any]] = {}
    two_lines: Optional[Dict[str, Any]] = {}
    one_line: Optional[Dict[str, Any]] = {}
    spotlight: Optional[Dict[str, Any]] = {}
    split_screen: Optional[Dict[str, Any]] = {}
    minimal: Optional[Dict[str, Any]] = {}
    dynamic: Optional[Dict[str, Any]] = {}

class StyleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    three_lines: Optional[Dict[str, Any]] = None
    two_lines: Optional[Dict[str, Any]] = None
    one_line: Optional[Dict[str, Any]] = None
    spotlight: Optional[Dict[str, Any]] = None
    split_screen: Optional[Dict[str, Any]] = None
    minimal: Optional[Dict[str, Any]] = None
    dynamic: Optional[Dict[str, Any]] = None

class StyleResponse(StyleBase):
    id: int
    three_lines: Dict[str, Any]
    two_lines: Dict[str, Any]
    one_line: Dict[str, Any]
    spotlight: Dict[str, Any]
    split_screen: Dict[str, Any]
    minimal: Dict[str, Any]
    dynamic: Dict[str, Any]
    is_default: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============== Video Schemas (DEFINE BEFORE UserWithVideos) ==============

class VideoBase(BaseModel):
    name: Optional[str] = None
    transcript: Optional[str] = None

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    name: Optional[str] = None
    transcript: Optional[Dict[str, Any]] = None  # Changed from str to accept JSON
    low_res_url: Optional[str] = None
    high_res_url: Optional[str] = None
    current_style: Optional[Dict[str, Any]] = None
    style_id: Optional[int] = None
    status: Optional[str] = None  # Add status field


class VideoCreate(BaseModel):
    name: Optional[str] = None
    # No longer need to pass URLs - they come from upload

class VideoUploadResponse(BaseModel):
    video_id: int
    status: str
    message: str
    original_url: str
    name: str
    user_id: int

class VideoResponse(BaseModel):
    id: int
    name: Optional[str]
    transcript: Optional[str]
    original_url: Optional[str]
    low_res_url: Optional[str]
    high_res_url: Optional[str]
    original_filename: Optional[str]
    content_type: Optional[str]
    file_size: Optional[int]
    duration: Optional[int]
    current_style: Dict[str, Any]
    status: str
    style_id: Optional[int]
    owner_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class VideoWithStyle(VideoResponse):
    style: Optional[StyleResponse] = None
    
    class Config:
        from_attributes = True
# Keep other schemas same...


# ============== User Schemas (CONTINUED - now can reference VideoResponse) ==============

class UserResponse(UserBase):
    id: int
    credits: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserWithVideos(UserResponse):
    videos: List[VideoResponse] = []  # Now VideoResponse is defined!
    
    class Config:
        from_attributes = True


# ============== Auth Schemas ==============

class GoogleAuthRequest(BaseModel):
    token: str  # Google ID token from frontend

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class GoogleUserInfo(BaseModel):
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    sub: str  # Google's user ID

# Request model for the frontend payload
class StyleConfig(BaseModel):
    """Style configuration from frontend"""
    template: str
    font: str
    fontSize: int
    position: str
    color: str
    backgroundColor: str
    maxLines: int
    # Add other fields as needed based on your frontend config


class GenerateCaptionsRequest(BaseModel):
    """Request body for generate captions endpoint"""
    user_id: str
    video_id: str
    video_url: str
    style_config: Dict[str, Any]  # Flexible to accept any style config structure
    video_filename: str
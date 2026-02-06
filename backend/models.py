# backend/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from datetime import datetime
__all__ = ['Base', 'User', 'Video', 'Style']

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    google_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)  # Google profile picture
    credits = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    subscription = Column(String, default="Free")
    # Relationships
    videos = relationship("Video", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(email={self.email}, credits={self.credits})>"


# backend/models.py

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    
    # Transcript - can be added later after processing
    transcript = Column(JSON, nullable=True)
    
    # Video URLs - populated immediately on upload
    original_url = Column(String, nullable=True)  # Original uploaded file
    low_res_url = Column(String, nullable=True)   # Processed low res
    high_res_url = Column(String, nullable=True)  # Processed high res
    
    # File metadata
    original_filename = Column(String, nullable=True)
    content_type = Column(String, nullable=True)  # video/mp4, audio/mp3, etc.
    file_size = Column(Integer, nullable=True)    # in bytes
    duration = Column(Integer, nullable=True)     # seconds
    
    # Current active style configuration (JSON)
    current_style = Column(JSON, default=dict)
    
    # Foreign keys
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    style_id = Column(Integer, ForeignKey("styles.id"), nullable=True)
    
    # Processing status
    status = Column(String, default="uploaded")  # uploaded, processing, ready, error
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="videos")
    style = relationship("Style", back_populates="videos")
    
    def __repr__(self):
        return f"<Video(id={self.id}, status={self.status}, owner={self.owner.email})>"


class Style(Base):
    __tablename__ = "styles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Style template name
    description = Column(String, nullable=True)
    
    # Different style configurations as JSON
    matt = Column(JSON, default=list)      # Three line layout config
    three_lines = Column(JSON, default=list)      # Three line layout config
    two_lines = Column(JSON, default=list)        # Two line layout config
    one_line = Column(JSON, default=list)         # Single line layout config
    spotlight = Column(JSON, default=list)        # Spotlight style config
    split_screen = Column(JSON, default=list)     # Split screen config
    minimal = Column(JSON, default=list)          # Minimal style config
    dynamic = Column(JSON, default=list)          # Dynamic animated config
    
    # User who created this style (optional, for user-specific styles)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    is_default = Column(Integer, default=0)  # 1 if system default, 0 if user-created
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    videos = relationship("Video", back_populates="style")
    
    def __repr__(self):
        return f"<Style(name={self.name})>"
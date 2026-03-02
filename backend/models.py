# backend/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID



__all__ = ['Base', 'User', 'Video', 'Style', 'RenderJob',  'Referrer', 'Referral']

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    google_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)  # Google profile picture
    credits = Column(Integer, default=2)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    subscription = Column(String, default="Free")
    # Relationships
    videos = relationship("Video", back_populates="owner", cascade="all, delete-orphan")

    referred_by_code = Column(String, nullable=True)   # stores "manish98" at signup
    # referrer_profile = relationship("Referrer", back_populates="user", uselist=False)
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

    # video info
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    fps = Column(Float, nullable=True)
    duration = Column(Float, nullable=True)     # seconds
    
    # Current active style configuration (JSON)
    current_style = Column(JSON, default=dict)
    all_styles_mapping = Column(JSON, default=dict)
    caption_padding = Column(Integer, nullable=True)
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

    # render job id
    render_job_id = Column(UUID(as_uuid=True), nullable=True)

    # these are for generating caption phase not the final render phase
    progress = Column(Integer, default=0)        # 0-100
    current_step = Column(String, nullable=True) 

    language = Column(String, default='en')
    
    def __repr__(self):
        return f"<Video(id={self.id}, status={self.status}, owner={self.owner.email})>"


class Style(Base):
    __tablename__ = "styles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Style template name
    description = Column(String, nullable=True)
    
    # Different style configurations as JSON
    styled_transcript = Column(JSON, default=list)      # Three line layout config
   
    # User who created this style (optional, for user-specific styles)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    is_default = Column(Integer, default=0)  # 1 if system default, 0 if user-created
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    videos = relationship("Video", back_populates="style")
    
    def __repr__(self):
        return f"<Style(name={self.name})>"





### Render Job model
class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)

    status = Column(String, default="queued")
    progress = Column(Float, default=0)

    input_props = Column(JSON, nullable=False)

    output_url = Column(Text)
    error = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)




## REFERRAL

class Referrer(Base):
    __tablename__ = "referrers"

    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)  # one link per user
    google_id = Column(String, unique=True, index=True, nullable=True)
    code = Column(String, unique=True, index=True, nullable=False)  # e.g. "manish98"

    clicks = Column(Integer, default=0)
    signups = Column(Integer, default=0)
    customers = Column(Integer, default=0)

    # earnings in cents
    total_earned_cents = Column(Integer, default=0)

    # Payout / profile fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    paypal_email = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships

    referrals = relationship("Referral", back_populates="referrer")
    payouts = relationship("Payout", back_populates="referrer")

# New Payout model — add this:
class Payout(Base):
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("referrers.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String, default="pending")   # pending | paid | failed
    note = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

    referrer = relationship("Referrer", back_populates="payouts")


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("referrers.id"), nullable=False)
    referred_user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)  # one referrer per user

    converted = Column(Integer, default=0)  # 0 = signed up, 1 = paid
    commission_cents = Column(Integer, default=0)  # commission earned from this referral

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    converted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    referrer = relationship("Referrer", back_populates="referrals")
    referred_user = relationship("User", foreign_keys=[referred_user_id])



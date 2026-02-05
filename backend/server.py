# backend/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine, Base
from backend.routers import auth, users, videos, styles, uploads
from backend.config import settings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Video Editor API",
    description="API for video editing with transcript and styles",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(videos.router)
app.include_router(styles.router)
app.include_router(uploads.router)  # Uploads router handles the upload endpoint


@app.get("/")
def read_root():
    return {"message": "Video Editor API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
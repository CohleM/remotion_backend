# backend/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend import crud, schemas
from backend.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=List[schemas.UserResponse])
def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Get all users (admin only - add admin check as needed)
    """
    users = db.query(crud.models.User).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=schemas.UserWithVideos)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Get specific user by ID
    """
    # Users can only view their own profile (add admin override if needed)
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this user")
    
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return schemas.UserWithVideos.model_validate(user)
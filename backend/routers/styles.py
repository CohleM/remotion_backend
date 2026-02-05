# backend/routers/styles.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend import crud, schemas
from backend.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/styles", tags=["styles"])

@router.post("/", response_model=schemas.StyleResponse)
def create_style(
    style: schemas.StyleCreate,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Create a new custom style
    """
    new_style = crud.create_style(db, style, creator_id=current_user.id)
    return new_style

@router.get("/", response_model=List[schemas.StyleResponse])
def get_styles(
    include_default: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Get all available styles (default + user-created)
    """
    styles = crud.get_styles(db, skip=skip, limit=limit, include_default=include_default)
    return styles

@router.get("/defaults", response_model=List[schemas.StyleResponse])
def get_default_styles(
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Get only system default styles
    """
    return crud.get_default_styles(db)

@router.get("/{style_id}", response_model=schemas.StyleResponse)
def get_style(
    style_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Get specific style by ID
    """
    style = crud.get_style(db, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    return style

@router.put("/{style_id}", response_model=schemas.StyleResponse)
def update_style(
    style_id: int,
    style_update: schemas.StyleUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Update a style (only creator can update)
    """
    style = crud.get_style(db, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    
    # Only allow update if user created this style or is admin
    if style.creator_id != current_user.id and style.is_default == 0:
        raise HTTPException(status_code=403, detail="Not authorized to update this style")
    
    updated_style = crud.update_style(db, style_id, style_update)
    return updated_style

@router.delete("/{style_id}")
def delete_style(
    style_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Delete a style (only creator can delete, cannot delete defaults)
    """
    style = crud.get_style(db, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    
    if style.is_default == 1:
        raise HTTPException(status_code=403, detail="Cannot delete default styles")
    
    if style.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this style")
    
    success = crud.delete_style(db, style_id)
    if success:
        return {"message": "Style deleted successfully"}
    raise HTTPException(status_code=500, detail="Failed to delete style")
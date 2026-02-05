# backend/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import datetime, timedelta
from typing import Optional

from backend import crud, schemas
from backend.database import get_db
from backend.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_google_token(token: str) -> schemas.GoogleUserInfo:
    """
    Verify Google ID token and return user info
    """
    try:
        # Verify the token with Google's certs
        idinfo = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10
        )
        
        # Verify issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        
        return schemas.GoogleUserInfo(
            email=idinfo['email'],
            name=idinfo.get('name'),
            picture=idinfo.get('picture'),
            sub=idinfo['sub']  # Google's unique user ID
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> schemas.UserResponse:
    """
    Dependency to get current authenticated user from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user(db, int(user_id))
    if user is None:
        raise credentials_exception
    
    return schemas.UserResponse.model_validate(user)

@router.post("/google", response_model=schemas.TokenResponse)
async def google_auth(
    auth_request: schemas.GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with Google ID token.
    Creates new user if doesn't exist.
    """
    # Verify Google token
    google_user = verify_google_token(auth_request.token)

    print('google user', google_user) 
    # Check if user exists
    user = crud.get_user_by_google_id(db, google_user.sub)
    print('user', user) 
    
    if not user:
        # Check if email exists (user might have signed up before)
        existing_user = crud.get_user_by_email(db, google_user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered with different method"
            )
        
        # Create new user
        user_create = schemas.UserCreate(
            email=google_user.email,
            name=google_user.name,
            picture=google_user.picture,
            google_id=google_user.sub
        )
        user = crud.create_user(db, user_create)
    
    # Create JWT token
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )
    
    return schemas.TokenResponse(
        access_token=access_token,
        user=schemas.UserResponse.model_validate(user)
    )

@router.get("/me", response_model=schemas.UserWithVideos)
async def get_current_user_info(
    current_user: schemas.UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user info with their videos
    """
    user = crud.get_user(db, current_user.id)
    return schemas.UserWithVideos.model_validate(user)

@router.post("/refresh")
async def refresh_token(current_user: schemas.UserResponse = Depends(get_current_user)):
    """
    Refresh access token
    """
    new_token = create_access_token(
        data={"sub": str(current_user.id)}
    )
    return {"access_token": new_token, "token_type": "bearer"}
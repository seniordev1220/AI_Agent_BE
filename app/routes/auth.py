from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from ..schemas.user import UserCreate, UserResponse, Token, GoogleAuth
from ..models.user import User
from ..utils.password import verify_password, get_password_hash
from ..utils.auth import create_access_token
from ..config import config
from ..services.settings import SettingsService
from ..utils.activity_logger import log_activity
from ..services.trial_service import TrialService
from ..utils.api_key_validator import generate_finiite_api_key, validate_finiite_api_key

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=UserResponse)
async def signup(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Check if email login is enabled
    auth_settings = SettingsService.get_auth_settings(db)
    if auth_settings and not auth_settings.email_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email registration is disabled. Please use SSO.",
        )

    # Check if user exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    finiite_api_key = generate_finiite_api_key()
    db_user = User(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        hashed_password=hashed_password,
        provider="credentials",
        finiite_api_key=finiite_api_key
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Start trial period
    TrialService.start_trial(db, db_user)

    # Log activity
    await log_activity(
        db=db,
        user_id=db_user.id,
        activity_type="signup",
        description="User signed up and trial period started",
        request=request,
        metadata={
            "provider": "credentials",
            "trial_start": db_user.trial_start.isoformat(),
            "trial_end": db_user.trial_end.isoformat()
        }
    )

    return db_user

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Check if email login is enabled
    auth_settings = SettingsService.get_auth_settings(db)
    if auth_settings and not auth_settings.email_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email login is disabled. Please use SSO.",
        )

    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        # Log failed login attempt
        if user:
            await log_activity(
                db=db,
                user_id=user.id,
                activity_type="login_failed",
                description="Failed login attempt",
                request=request,
                metadata={"reason": "incorrect_password"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=int(config["ACCESS_TOKEN_EXPIRE_MINUTES"]))
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # Log successful login
    await log_activity(
        db=db,
        user_id=user.id,
        activity_type="login",
        description="User logged in successfully",
        request=request,
        metadata={"provider": "credentials"}
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=Token)
def google_auth(user_data: GoogleAuth, db: Session = Depends(get_db)):
    """Handle Google OAuth authentication"""
    # Check if user exists
    db_user = db.query(User).filter(User.email == user_data.email).first()
    
    if db_user:
        # Update existing user if needed
        db_user.first_name = user_data.first_name
        db_user.last_name = user_data.last_name
        if not db_user.provider:
            db_user.provider = "google"
        db.commit()
    else:
        # Create new user
        finiite_api_key = generate_finiite_api_key()
        db_user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            provider="google",
            finiite_api_key=finiite_api_key
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token_expires = timedelta(minutes=int(config["ACCESS_TOKEN_EXPIRE_MINUTES"]))
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/validate-finiite-key/{api_key}", response_model=UserResponse)
async def validate_finiite_key(api_key: str, db: Session = Depends(get_db)):
    """Validate Finiite API key and return user information"""
    # Check if API key is valid
    if not await validate_finiite_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Finiite API key"
        )
    
    # Get user by API key
    user = db.query(User).filter(User.finiite_api_key == api_key).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

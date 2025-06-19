from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.user import UserProfile, UserUpdate, PasswordChange, UserCreate, UserResponse
from ..models.user import User
from ..utils.auth import get_current_user, get_current_admin_user
from ..utils.password import verify_password, get_password_hash
from ..services.trial_service import TrialService

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create users"
        )

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        hashed_password=get_password_hash(user_data.password),
        role="user"  # Default role for new users
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a user (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete users"
        )

    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if trying to delete another admin
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin users"
        )

    db.delete(user)
    db.commit()
    return None

@router.get("", response_model=List[UserProfile])
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view all users"
        )
    
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/me", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user's profile
    """
    return current_user

@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile
    """
    # Check if email is being updated and if it's already taken
    if user_update.email and user_update.email != current_user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Update user fields
    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user 

@router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    passwords: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user's password
    """
    # Verify current password
    if not verify_password(passwords.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Hash new password and update
    current_user.hashed_password = get_password_hash(passwords.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.get("/{user_id}", response_model=UserProfile)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user profile by user ID. Users can view their own profile, while admins can view any profile.
    """
    # Allow users to view their own profile or admins to view any profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view user details"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.get("/trial-status")
def get_trial_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current user's trial status and limits"""
    trial_status = TrialService.check_trial_status(db, current_user)
    
    # If user has an active trial, include the limits
    if trial_status['trial_active']:
        trial_status['limits'] = TrialService.get_trial_limits()
    
    return trial_status

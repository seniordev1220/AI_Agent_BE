from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.user import UserProfile, UserUpdate, PasswordChange, UserCreate, UserResponse, UserAdminCreate, UserAdminUpdate, UserWithSubscription
from ..models.user import User
from ..models.price_plan import PricePlan
from ..models.subscription import Subscription
from ..utils.auth import get_current_user, get_current_admin_user
from ..utils.password import verify_password, get_password_hash
from ..services.trial_service import TrialService
from ..services.subscription_service import SubscriptionService
from decimal import Decimal
from ..utils.api_key_validator import generate_finiite_api_key
from ..models.user_activity import UserActivity

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=UserWithSubscription, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserAdminCreate,
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
    finiite_api_key = generate_finiite_api_key()
    new_user = User(
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        storage_limit_bytes=user_data.storage_limit_bytes,
        max_users=user_data.max_users,
        finiite_api_key=finiite_api_key
    )
    
    if user_data.password:
        new_user.hashed_password = get_password_hash(user_data.password)
    
    db.add(new_user)
    db.flush()  # Flush to get the user ID
    
    # Create custom subscription if prices are provided
    if user_data.custom_monthly_price or user_data.custom_annual_price:
        monthly_amount = int(Decimal(str(user_data.custom_monthly_price or 0)) * 100)  # Convert to cents
        annual_amount = int(Decimal(str(user_data.custom_annual_price or 0)) * 100)  # Convert to cents
        
        await SubscriptionService.create_or_update_admin_subscription(
            db=db,
            user=new_user,
            monthly_amount=monthly_amount if user_data.custom_monthly_price else None,
            annual_amount=annual_amount if user_data.custom_annual_price else None,
            plan_name=f"Custom Plan - {new_user.email}"
        )
    
    db.commit()
    db.refresh(new_user)
    
    # Format response
    response = UserWithSubscription.from_orm(new_user)
    if new_user.subscription:
        response.subscription = {
            "plan_type": new_user.subscription.plan_type,
            "billing_interval": new_user.subscription.billing_interval,
            "status": new_user.subscription.status,
            "stripe_customer_id": new_user.stripe_customer_id
        }
    
    return response

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

    # Cancel subscription if exists
    if user.subscription:
        await SubscriptionService.cancel_subscription(user.subscription.stripe_subscription_id)

    # Delete all user activities first
    db.query(UserActivity).filter(UserActivity.user_id == user_id).delete()
    
    # Delete the user
    db.delete(user)
    db.commit()
    return None

@router.get("", response_model=List[UserWithSubscription])
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
    
    # Format response with subscription info
    response = []
    for user in users:
        # First convert user to dict to avoid validation errors
        user_dict = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "storage_limit_bytes": user.storage_limit_bytes,
            "storage_used_bytes": user.storage_used_bytes,
            "max_users": user.max_users,
            "current_users": user.current_users,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "finiite_api_key": user.finiite_api_key,
            "subscription": None
        }
        
        if user.subscription:
            user_dict["subscription"] = {
                "plan_type": user.subscription.plan_type,
                "billing_interval": user.subscription.billing_interval,
                "status": user.subscription.status
            }
        
        user_data = UserWithSubscription(**user_dict)
        response.append(user_data)
    
    return response

@router.get("/me", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user's profile
    """
    return current_user

@router.put("/me", response_model=UserWithSubscription)
async def update_user_profile(
    user_update: UserAdminUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile
    """
    # Only admin can update certain fields
    if current_user.role != "admin":
        restricted_fields = {"role", "storage_limit_bytes", "max_users", "custom_monthly_price", "custom_annual_price"}
        if any(field in user_update.dict(exclude_unset=True) for field in restricted_fields):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update these fields"
            )

    # Check if email is being updated and if it's already taken
    if user_update.email and user_update.email != current_user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Update user fields
    for field, value in user_update.dict(exclude_unset=True).items():
        if field not in ['custom_monthly_price', 'custom_annual_price'] and value is not None:
            setattr(current_user, field, value)

    # Update custom subscription if prices are provided and user is admin
    if current_user.role == "admin" and (user_update.custom_monthly_price is not None or user_update.custom_annual_price is not None):
        monthly_amount = int(Decimal(str(user_update.custom_monthly_price or 0)) * 100)  # Convert to cents
        annual_amount = int(Decimal(str(user_update.custom_annual_price or 0)) * 100)  # Convert to cents
        
        await SubscriptionService.create_or_update_admin_subscription(
            db=db,
            user=current_user,
            monthly_amount=monthly_amount if user_update.custom_monthly_price else None,
            annual_amount=annual_amount if user_update.custom_annual_price else None,
            plan_name=f"Custom Plan - {current_user.email}"
        )

    db.commit()
    db.refresh(current_user)

    # Format response
    response = UserWithSubscription.from_orm(current_user)
    if current_user.subscription:
        response.subscription = {
            "plan_type": current_user.subscription.plan_type,
            "billing_interval": current_user.subscription.billing_interval,
            "status": current_user.subscription.status,
            "stripe_customer_id": current_user.stripe_customer_id
        }

    return response

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

@router.put("/{user_id}", response_model=UserWithSubscription)
async def update_user(
    user_id: int,
    user_update: UserAdminUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a user (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update users"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if email is being updated and if it's already taken
    if user_update.email and user_update.email != user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Update user fields
    for field, value in user_update.dict(exclude_unset=True).items():
        if field not in ['custom_monthly_price', 'custom_annual_price'] and value is not None:
            setattr(user, field, value)

    # Update custom subscription if prices are provided
    if user_update.custom_monthly_price is not None or user_update.custom_annual_price is not None:
        monthly_amount = int(Decimal(str(user_update.custom_monthly_price or 0)) * 100)  # Convert to cents
        annual_amount = int(Decimal(str(user_update.custom_annual_price or 0)) * 100)  # Convert to cents
        
        await SubscriptionService.create_or_update_admin_subscription(
            db=db,
            user=user,
            monthly_amount=monthly_amount if user_update.custom_monthly_price else None,
            annual_amount=annual_amount if user_update.custom_annual_price else None,
            plan_name=f"Custom Plan - {user.email}"
        )

    db.commit()
    db.refresh(user)

    # Format response
    response = UserWithSubscription.from_orm(user)
    if user.subscription:
        response.subscription = {
            "plan_type": user.subscription.plan_type,
            "billing_interval": user.subscription.billing_interval,
            "status": user.subscription.status,
            "stripe_customer_id": user.stripe_customer_id
        }

    return response

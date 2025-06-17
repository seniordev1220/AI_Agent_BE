from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.activity_service import ActivityService
from app.models.user_activity import UserActivity
from app.utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/activities", tags=["activities"])

@router.get("/me", response_model=List[dict])
async def get_my_activities(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    activity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get activities for the current user."""
    activity_service = ActivityService(db)
    activities = activity_service.get_user_activities(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        activity_type=activity_type
    )
    
    return [
        {
            "id": activity.id,
            "activity_type": activity.activity_type,
            "description": activity.description,
            "metadata": activity.activity_metadata,
            "created_at": activity.created_at,
            "ip_address": activity.ip_address,
            "user_agent": activity.user_agent
        }
        for activity in activities
    ]

@router.get("/recent", response_model=List[dict])
async def get_recent_activities(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    activity_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent activities across all users (admin only)."""
    # Check if user has admin role
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view all activities")
    
    activity_service = ActivityService(db)
    activities = activity_service.get_recent_activities(
        skip=skip,
        limit=limit,
        activity_type=activity_type
    )
    
    return [
        {
            "id": activity.id,
            "user_id": activity.user_id,
            "activity_type": activity.activity_type,
            "description": activity.description,
            "metadata": activity.activity_metadata,
            "created_at": activity.created_at,
            "ip_address": activity.ip_address,
            "user_agent": activity.user_agent
        }
        for activity in activities
    ] 

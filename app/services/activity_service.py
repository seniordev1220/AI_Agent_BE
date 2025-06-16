from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.user_activity import UserActivity
from app.models.user import User

class ActivityService:
    def __init__(self, db: Session):
        self.db = db

    async def log_activity(
        self,
        user_id: int,
        activity_type: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> UserActivity:
        """
        Log a user activity.
        
        Args:
            user_id: The ID of the user performing the activity
            activity_type: Type of activity (e.g., 'login', 'chat', 'settings_update')
            description: Optional description of the activity
            metadata: Optional additional data related to the activity
            request: Optional FastAPI request object to extract IP and user agent
        """
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            activity_metadata=metadata,
        )

        if request:
            activity.ip_address = request.client.host
            activity.user_agent = request.headers.get("user-agent")

        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        
        return activity

    def get_user_activities(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        activity_type: Optional[str] = None
    ) -> list[UserActivity]:
        """
        Get activities for a specific user.
        
        Args:
            user_id: The ID of the user
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            activity_type: Optional filter by activity type
        """
        query = self.db.query(UserActivity).filter(UserActivity.user_id == user_id)
        
        if activity_type:
            query = query.filter(UserActivity.activity_type == activity_type)
            
        return query.order_by(UserActivity.created_at.desc()).offset(skip).limit(limit).all()

    def get_recent_activities(
        self,
        skip: int = 0,
        limit: int = 100,
        activity_type: Optional[str] = None
    ) -> list[UserActivity]:
        """
        Get recent activities across all users.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            activity_type: Optional filter by activity type
        """
        query = self.db.query(UserActivity)
        
        if activity_type:
            query = query.filter(UserActivity.activity_type == activity_type)
            
        return query.order_by(UserActivity.created_at.desc()).offset(skip).limit(limit).all() 

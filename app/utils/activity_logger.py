from fastapi import Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.services.activity_service import ActivityService

async def log_activity(
    db: Session,
    user_id: int,
    activity_type: str,
    description: str,
    request: Optional[Request] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Utility function to log user activities.
    
    Args:
        db: Database session
        user_id: ID of the user performing the action
        activity_type: Type of activity (e.g., 'login', 'chat', 'agent_create')
        description: Description of the activity
        request: Optional FastAPI request object
        metadata: Optional additional data about the activity
    """
    activity_service = ActivityService(db)
    await activity_service.log_activity(
        user_id=user_id,
        activity_type=activity_type,
        description=description,
        metadata=metadata,
        request=request
    ) 

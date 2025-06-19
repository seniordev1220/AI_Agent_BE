from sqlalchemy.orm import Session
from typing import Dict, Optional
from ..models.user import User
from ..models.subscription import Subscription
from ..models.price_plan import PricePlan
from fastapi import HTTPException
from sqlalchemy import func

class SubscriptionService:
    PLAN_LIMITS = {
        "individual": {
            "storage_mb": 50,  # 50 MB
            "agents": 1,
            "workflow_automation": False
        },
        "standard": {
            "storage_mb": 1024,  # 1 GB
            "agents": 10,
            "workflow_automation": True
        },
        "smb": {
            "storage_mb": 10240,  # 10 GB
            "agents": float('inf'),  # Unlimited
            "workflow_automation": True
        }
    }

    @staticmethod
    def get_user_limits(db: Session, user: User) -> Dict:
        """Get the limits for a user based on their subscription"""
        if not user.subscription:
            return None

        subscription = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == "active"
        ).first()

        if not subscription:
            return None

        return SubscriptionService.PLAN_LIMITS.get(subscription.plan_type.lower())

    @staticmethod
    def check_storage_limit(db: Session, user: User, additional_size_bytes: int = 0) -> bool:
        """Check if user is within storage limits"""
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False

        # Get current storage usage from data sources
        from ..models.data_source import DataSource
        current_usage = db.query(DataSource).filter(
            DataSource.user_id == user.id
        ).with_entities(
            func.sum(DataSource.raw_size_bytes + DataSource.processed_size_bytes)
        ).scalar() or 0

        # Convert limit to bytes
        limit_bytes = limits["storage_mb"] * 1024 * 1024

        # Check if adding new data would exceed limit
        if current_usage + additional_size_bytes > limit_bytes:
            raise HTTPException(
                status_code=403,
                detail=f"Storage limit exceeded. Your plan allows {limits['storage_mb']}MB of storage."
            )
        return True

    @staticmethod
    def check_agent_limit(db: Session, user: User, current_count: Optional[int] = None) -> bool:
        """Check if user is within agent limits"""
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False

        if current_count is None:
            from ..models.agent import Agent
            current_count = db.query(Agent).filter(Agent.user_id == user.id).count()

        if current_count >= limits["agents"]:
            raise HTTPException(
                status_code=403,
                detail=f"Agent limit reached. Your plan allows {limits['agents']} AI agents."
            )
        return True

    @staticmethod
    def can_use_workflow_automation(db: Session, user: User) -> bool:
        """Check if user can use workflow automation"""
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False
        return limits["workflow_automation"] 

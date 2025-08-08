from sqlalchemy.orm import Session
from typing import Dict, Optional, Tuple
from ..models.user import User
from ..models.subscription import Subscription
from ..models.price_plan import PricePlan
from fastapi import HTTPException
from sqlalchemy import func
import stripe
from decimal import Decimal
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

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
        """Get the limits for a user based on their subscription or activation status"""
        # For users with activation code (trial_status = 'active' and no subscription)
        if user.trial_status == 'active' and not user.subscription:
            return {
                "storage_mb": user.storage_limit_bytes / (1024 * 1024),  # Convert bytes to MB
                "agents": 10,  # Fixed limit for activation code users
                "workflow_automation": True
            }

        # For users with subscription
        if user.subscription and user.subscription.status == "active":
            if user.subscription.plan_type == "custom":
                return {
                    "storage_mb": user.storage_limit_bytes / (1024 * 1024),
                    "agents": user.max_users,
                    "workflow_automation": True
                }
            return SubscriptionService.PLAN_LIMITS.get(user.subscription.plan_type.lower())

        # For trial users or others
        return None

    @staticmethod
    def check_storage_limit(db: Session, user: User, additional_size_bytes: int = 0) -> bool:
        """Check if user is within storage limits"""
        # Test accounts have no limits
        if user.is_test_account:
            return True
            
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
        # Test accounts have no limits
        if user.is_test_account:
            return True
            
        limits = SubscriptionService.get_user_limits(db, user)
        if not limits:
            return False

        if current_count is None:
            from ..models.agent import Agent
            current_count = db.query(Agent).filter(Agent.user_id == user.id).count()

        # For activation code users, enforce strict limit of 10 agents
        if user.trial_status == 'active' and not user.subscription:
            if current_count >= 10:
                raise HTTPException(
                    status_code=403,
                    detail="You have reached the maximum limit of 10 agents with your activation code."
                )
            return True

        # For subscription users, check plan limits
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

    @staticmethod
    async def create_stripe_customer(user: User) -> str:
        """Create a Stripe customer for a user."""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    "user_id": str(user.id)
                }
            )
            return customer.id
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ... [rest of the file remains unchanged]
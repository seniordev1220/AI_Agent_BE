from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models.user import User
from ..models.subscription import Subscription
from fastapi import HTTPException
from datetime import timezone

class TrialService:
    TRIAL_DURATION_DAYS = 14
    TRIAL_LIMITS = {
        'agents': 1,  # Number of AI agents allowed
        'storage_mb': 10,  # Storage limit in MB
        'messages_per_day': 50  # Number of messages per day
    }

    @staticmethod
    def start_trial(db: Session, user: User) -> None:
        """Start the trial period for a new user"""
        now = datetime.now(timezone.utc)
        user.trial_start = now
        user.trial_end = now + timedelta(days=TrialService.TRIAL_DURATION_DAYS)
        user.trial_status = 'active'
        db.commit()

    @staticmethod
    def check_trial_status(db: Session, user: User) -> dict:
        """Check the trial status and return trial information"""
        if user.subscription:
            return {
                'has_subscription': True,
                'trial_active': False,
                'trial_expired': False,
                'days_remaining': 0,
                'message': 'User has an active subscription'
            }

        if not user.trial_start or not user.trial_end:
            TrialService.start_trial(db, user)
            return {
                'has_subscription': False,
                'trial_active': True,
                'trial_expired': False,
                'days_remaining': TrialService.TRIAL_DURATION_DAYS,
                'message': f'Trial started. {TrialService.TRIAL_DURATION_DAYS} days remaining'
            }

        now = datetime.now(timezone.utc)
        if user.trial_end is None:
            TrialService.start_trial(db, user)
            return {
                'has_subscription': False,
                'trial_active': True,
                'trial_expired': False,
                'days_remaining': TrialService.TRIAL_DURATION_DAYS,
                'message': f'Trial started. {TrialService.TRIAL_DURATION_DAYS} days remaining'
            }

        if now > user.trial_end:
            if user.trial_status != 'expired':
                user.trial_status = 'expired'
                db.commit()
            return {
                'has_subscription': False,
                'trial_active': False,
                'trial_expired': True,
                'days_remaining': 0,
                'message': 'Trial period has expired. Please subscribe to continue using the service.'
            }

        days_remaining = (user.trial_end - now).days
        return {
            'has_subscription': False,
            'trial_active': True,
            'trial_expired': False,
            'days_remaining': days_remaining,
            'message': f'Trial active. {days_remaining} days remaining'
        }

    @staticmethod
    def check_trial_limits(db: Session, user: User, resource_type: str, current_usage: int = None) -> bool:
        """
        Check if the user has exceeded trial limits
        Returns True if within limits, False if exceeded
        """
        # If user has subscription, no limits apply
        if user.subscription:
            return True

        # Check if trial is active
        trial_status = TrialService.check_trial_status(db, user)
        if not trial_status['trial_active']:
            raise HTTPException(
                status_code=403,
                detail="Trial period has expired. Please subscribe to continue using the service."
            )

        # Check specific resource limits
        if resource_type not in TrialService.TRIAL_LIMITS:
            return True

        limit = TrialService.TRIAL_LIMITS[resource_type]
        if current_usage is not None and current_usage >= limit:
            raise HTTPException(
                status_code=403,
                detail=f"Trial limit reached for {resource_type}. Please subscribe to increase your limits."
            )

        return True

    @staticmethod
    def get_trial_limits() -> dict:
        """Return the trial limits"""
        return TrialService.TRIAL_LIMITS 

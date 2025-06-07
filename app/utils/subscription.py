from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models.user import User
from ..models.subscription import Subscription
from ..utils.auth import get_current_user

async def check_active_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user has an active subscription or is in trial period.
    Raise HTTPException if subscription is inactive or trial has ended.
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription found. Please subscribe to access this feature."
        )

    now = datetime.utcnow()

    # Check if in trial period
    if subscription.status == 'trialing' and subscription.trial_end and subscription.trial_end > now:
        return subscription

    # Check if subscription is active and not past due
    if subscription.status not in ['active', 'trialing']:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription is not active. Please check your payment status."
        )

    # Check if subscription period has ended
    if subscription.current_period_end and subscription.current_period_end < now:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription period has ended. Please renew your subscription."
        )

    return subscription 

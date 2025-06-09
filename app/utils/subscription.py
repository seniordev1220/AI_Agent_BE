from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
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
        # Create a trial subscription for the user if they don't have one
        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        subscription = Subscription(
            user_id=current_user.id,
            plan_type='INDIVIDUAL',
            status='trialing',
            trial_end=trial_end,
            current_period_end=trial_end,
            seats=1
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription

    now = datetime.now(timezone.utc)

    # Check if in trial period
    if subscription.status == 'trialing':
        if subscription.trial_end and subscription.trial_end > now:
            # Valid trial period
            return subscription
        else:
            # Trial has ended
            subscription.status = 'inactive'
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Your free trial has ended. Please subscribe to continue using all features."
            )

    # Check if subscription is active and not past due
    if subscription.status not in ['active', 'trialing']:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your subscription is not active. Please check your payment status or renew your subscription."
        )

    # Check if subscription period has ended
    if subscription.current_period_end and subscription.current_period_end < now:
        subscription.status = 'inactive'
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your subscription period has ended. Please renew your subscription to continue."
        )

    return subscription

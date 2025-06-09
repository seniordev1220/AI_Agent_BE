from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import stripe
from ..database import get_db
from ..models.user import User
from ..models.subscription import Subscription
from ..schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    PlanType,
    PLAN_PRICES
)
from ..utils.auth import get_current_user
# from ..config import settings
from ..config import config
import os

router = APIRouter(prefix="/subscription", tags=["Subscription"])

# Initialize Stripe with your secret key
# stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_key = config["STRIPE_SECRET_KEY"]

# Stripe Product IDs for each plan
STRIPE_PRODUCTS = {
    PlanType.INDIVIDUAL: {
        "monthly": "price_individual_monthly",
        "annual": "price_individual_annual",
    },
    PlanType.STANDARD: {
        "monthly": "price_standard_monthly",
        "annual": "price_standard_annual",
    },
    PlanType.SMB: {
        "monthly": "price_smb_monthly",
        "annual": "price_smb_annual",
    }
}

@router.post("", response_model=SubscriptionResponse)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    payment_method_id: str,
    is_annual: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new subscription with a 14-day trial"""
    
    # Check if user already has a subscription
    existing_subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()
    
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a subscription"
        )

    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                payment_method=payment_method_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        else:
            # Update payment method if customer exists
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=current_user.stripe_customer_id
            )
            stripe.Customer.modify(
                current_user.stripe_customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )

        # Calculate trial end date (14 days from now)
        trial_end = datetime.utcnow() + timedelta(days=14)

        # Create Stripe subscription with trial
        stripe_subscription = stripe.Subscription.create(
            customer=current_user.stripe_customer_id,
            items=[{
                'price': STRIPE_PRODUCTS[subscription_data.plan_type]['annual' if is_annual else 'monthly'],
                'quantity': subscription_data.seats
            }],
            trial_end=int(trial_end.timestamp()),
            payment_settings={
                'payment_method_types': ['card'],
                'save_default_payment_method': 'on_subscription'
            }
        )

        # Create subscription record in database
        db_subscription = Subscription(
            user_id=current_user.id,
            stripe_customer_id=current_user.stripe_customer_id,
            stripe_subscription_id=stripe_subscription.id,
            plan_type=subscription_data.plan_type,
            status='trialing',
            trial_end=trial_end,
            current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
            seats=subscription_data.seats
        )
        
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        
        return db_subscription

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=Optional[SubscriptionResponse])
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription"""
    return db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

@router.put("", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_data: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update subscription (seats or cancellation)"""
    
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    try:
        if subscription_data.seats is not None:
            # Update seats in Stripe
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    'id': stripe.Subscription.retrieve(subscription.stripe_subscription_id).items.data[0].id,
                    'quantity': subscription_data.seats
                }]
            )
            subscription.seats = subscription_data.seats

        if subscription_data.cancel_at_period_end is not None:
            if subscription_data.cancel_at_period_end:
                # Cancel at period end
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            else:
                # Resume subscription
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False
                )
            subscription.cancel_at_period_end = subscription_data.cancel_at_period_end

        db.commit()
        db.refresh(subscription)
        return subscription

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config["STRIPE_WEBHOOK_SECRET"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail='Invalid payload')
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail='Invalid signature')

    # Handle the event
    if event.type == 'customer.subscription.updated':
        await handle_subscription_updated(event.data.object)
    elif event.type == 'customer.subscription.deleted':
        await handle_subscription_deleted(event.data.object)

    return {"status": "success"}

async def handle_subscription_updated(subscription_object):
    """Handle subscription update webhook"""
    db = next(get_db())
    db_subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_object.id
    ).first()

    if db_subscription:
        db_subscription.status = subscription_object.status
        db_subscription.current_period_end = datetime.fromtimestamp(subscription_object.current_period_end)
        db.commit()

async def handle_subscription_deleted(subscription_object):
    """Handle subscription deletion webhook"""
    db = next(get_db())
    db_subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_object.id
    ).first()

    if db_subscription:
        db_subscription.status = 'canceled'
        db.commit()

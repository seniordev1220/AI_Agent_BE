from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, Literal
import stripe
from sqlalchemy.orm import Session
from ..config import config
from pydantic import BaseModel
from ..database import get_db
from ..models.subscription import Subscription
from ..models.payment import Payment
from ..models.user import User
from datetime import datetime
import uuid
import traceback
from ..utils.activity_logger import log_activity
from ..utils.auth import get_current_user

router = APIRouter(prefix="/payment", tags=["payment"])

# Initialize Stripe with the API key from environment variables
stripe.api_key = config["STRIPE_SECRET_KEY"]

# Price IDs for different plans and their seat prices
PRICE_IDS = {
    "individual": {
        "monthly": {
            "base": "price_1RYQV6IqfRSqLdqDCfQgwH6M",  # Base plan price
            "seat": "price_1RYbafIqfRSqLdqDJJt1Mtvz"   # $7 per additional seat
        },
        "annual": {
            "base": "price_1RYUbeIqfRSqLdqDHRsoKANR",  # Base plan price
            "seat": "price_1RYbbDIqfRSqLdqDsCr9GYkK"   # Annual seat price
        }
    },
    "standard": {
        "monthly": {
            "base": "price_1RYQiZIqfRSqLdqDetDS4LyJ",
            "seat": "price_1RYbbgIqfRSqLdqDpqIUHXdY"
        },
        "annual": {
            "base": "price_1RYUcJIqfRSqLdqDuSTUw4be",
            "seat": "price_1RYbc8IqfRSqLdqDmTYuLuDG"
        }
    },
    "smb": {
        "monthly": {
            "base": "price_1RYQjGIqfRSqLdqDD7xwlV0w",
            "seat": "price_1RYbcUIqfRSqLdqDvWcUSvv2"
        },
        "annual": {
            "base": "price_1RYUceIqfRSqLdqD9jNpbllm",
            "seat": "price_1RYbcvIqfRSqLdqDmV5KWCev"
        }
    }
}

class CreateCheckoutSessionRequest(BaseModel):
    plan_type: Literal["individual", "standard", "smb"]
    billing_interval: Literal["monthly", "annual"]
    base_seats: int
    additional_seats: int = 0
    additional_seats_price: float
    base_price: float
    total_price: float
    stripe_price_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class RetrieveSessionRequest(BaseModel):
    session_id: str

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    req: Request = None,
    db: Session = Depends(get_db)
):
    try:
        # Default URLs if not provided
        success_url = request.success_url or f"{config['FRONTEND_URL']}/payment/success"
        cancel_url = request.cancel_url or f"{config['FRONTEND_URL']}/dashboard/billing"

        # Get the appropriate price IDs based on plan type and billing interval
        price_ids = PRICE_IDS[request.plan_type][request.billing_interval]
        
        # Create line items for base plan
        line_items = [
            {
                "price": price_ids["base"],
                "quantity": 1,  # Base plan is always quantity 1
            }
        ]
        
        # Add additional seats if requested
        if request.additional_seats > 0:
            line_items.append({
                "price": price_ids["seat"],
                "quantity": request.additional_seats,  # Use the exact number of additional seats
            })

        # Create the checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="subscription",
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
            cancel_url=cancel_url,
            metadata={
                "plan_type": request.plan_type,
                "billing_interval": request.billing_interval,
                "base_seats": request.base_seats,
                "additional_seats": request.additional_seats,
                "total_seats": request.base_seats + request.additional_seats,
                "base_price": str(request.base_price),
                "additional_seats_price": str(request.additional_seats_price),
                "total_price": str(request.total_price)
            },
            allow_promotion_codes=True,
            client_reference_id=str(uuid.uuid4())
        )

        # Log activity for checkout session creation
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="checkout_session_create",
            description=f"Created checkout session for {request.plan_type} plan ({request.billing_interval})",
            request=req,
            metadata={
                "plan_type": request.plan_type,
                "billing_interval": request.billing_interval,
                "base_seats": request.base_seats,
                "additional_seats": request.additional_seats,
                "total_seats": request.base_seats + request.additional_seats,
                "base_price": request.base_price,
                "additional_seats_price": request.additional_seats_price,
                "total_price": request.total_price,
                "session_id": session.id
            }
        )

        return {"sessionId": session.id, "url": session.url}
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid plan type or billing interval")
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("Error details:", str(e))
        print("Traceback:", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/retrieve-checkout-session")
async def retrieve_checkout_session(
    request: RetrieveSessionRequest,
    db: Session = Depends(get_db)
):
    try:
        # Retrieve the checkout session
        session = stripe.checkout.Session.retrieve(
            request.session_id,
            expand=['payment_intent', 'subscription']
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.payment_status == 'paid':
            # Store the subscription data
            subscription = await store_subscription(session, db)

        return {
            "status": "success",
            "session": {
                "id": session.id,
                "payment_status": session.payment_status,
                "customer_email": session.customer_details.email if hasattr(session, 'customer_details') else None,
                "amount_total": session.amount_total / 100 if session.amount_total else None,
                "currency": session.currency,
                "subscription_id": session.subscription.id if session.subscription else None,
                "metadata": session.metadata
            }
        }
    except stripe.error.InvalidRequestError as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")
    except Exception as e:
        print("Error details:", str(e))
        print("Traceback:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Error processing payment session: {str(e)}")

async def store_subscription(session: stripe.checkout.Session, db: Session):
    """Helper function to store subscription data in database"""
    try:
        # Get the user from the customer email
        customer_email = session.customer_details.email
        if not customer_email:
            raise HTTPException(status_code=400, detail="Customer email not found in session")

        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user's trial status
        user.trial_status = 'active'
        user.trial_end = datetime.utcnow()

        # Get subscription data directly from the session
        subscription_data = session.subscription
        
        # Get subscription items
        subscription_items = []
        if subscription_data and hasattr(subscription_data, 'items'):
            items_list = subscription_data.items()
            if hasattr(items_list, 'data'):
                subscription_items = items_list.data
        
        # Get period dates from subscription items
        current_period_start = None
        current_period_end = None
        
        if subscription_items:
            for item in subscription_items:
                if not current_period_start or item.current_period_start < current_period_start:
                    current_period_start = item.current_period_start
                if not current_period_end or item.current_period_end > current_period_end:
                    current_period_end = item.current_period_end
        
        if not current_period_start:
            current_period_start = subscription_data.created

        # Get seat information from metadata
        base_seats = int(session.metadata.get('base_seats', 1))
        additional_seats = int(session.metadata.get('additional_seats', 0))
        total_seats = base_seats + additional_seats

        # Create or update subscription
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_data.id
        ).first()

        is_new_subscription = not subscription

        if not subscription:
            subscription = Subscription(
                user_id=user.id,
                stripe_subscription_id=subscription_data.id,
                plan_type=session.metadata.get('plan_type'),
                billing_interval=session.metadata.get('billing_interval'),
                seats=total_seats,  # Use total seats instead of separate base and additional seats
                status=subscription_data.status,
                current_period_start=datetime.fromtimestamp(current_period_start) if current_period_start else None,
                current_period_end=datetime.fromtimestamp(current_period_end) if current_period_end else None
            )
            db.add(subscription)
            db.flush()

        # Generate payment ID - use payment_intent if available, otherwise use subscription ID
        payment_id = session.payment_intent or session.subscription.id

        # Check if payment record already exists
        existing_payment = db.query(Payment).filter(
            Payment.stripe_payment_id == payment_id
        ).first()

        if not existing_payment:
            # Create payment record only if it doesn't exist
            payment = Payment(
                user_id=user.id,
                subscription_id=subscription.id,
                stripe_payment_id=payment_id,
                amount=session.amount_total if session.amount_total else 0,  # Convert from cents to dollars
                currency=session.currency.lower() if session.currency else 'usd',
                status=session.payment_status,
                payment_method='card'
            )
            db.add(payment)

        db.commit()

        # Log subscription activity
        await log_activity(
            db=db,
            user_id=user.id,
            activity_type="subscription_update" if not is_new_subscription else "subscription_create",
            description=f"{'Created' if is_new_subscription else 'Updated'} subscription for {session.metadata.get('plan_type')} plan",
            metadata={
                "subscription_id": subscription.id,
                "stripe_subscription_id": subscription_data.id,
                "plan_type": session.metadata.get('plan_type'),
                "billing_interval": session.metadata.get('billing_interval'),
                "seats": total_seats,
                "status": subscription_data.status,
                "is_new": is_new_subscription
            }
        )

        return subscription
    except Exception as e:
        db.rollback()
        print(f"Error storing subscription: {str(e)}")
        print(traceback.format_exc())
        raise 

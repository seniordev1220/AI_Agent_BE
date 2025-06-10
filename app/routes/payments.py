from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Literal
import stripe
from ..config import config
from pydantic import BaseModel

router = APIRouter(prefix="/payment", tags=["payment"])

# Initialize Stripe with the API key from environment variables
stripe.api_key = config["STRIPE_SECRET_KEY"]

# Price IDs for different plans
PRICE_IDS = {
    "individual": {
        "monthly": "price_1RYQV6IqfRSqLdqDCfQgwH6M",  # Replace with actual Individual Monthly price ID
        "annual": "price_1RYQTqIqfRSqLdqDK9UekeVQ"    # Replace with actual Individual Annual price ID
    },
    "standard": {
        "monthly": "price_1RYQiZIqfRSqLdqDetDS4LyJ",  # Replace with actual Standard Monthly price ID
        "annual": "price_1RYQi8IqfRSqLdqDRuZHYAA8"    # Replace with actual Standard Annual price ID
    },
    "smb": {
        "monthly": "price_1RYQjGIqfRSqLdqDD7xwlV0w",  # Replace with actual SMB Monthly price ID
        "annual": "price_1RYQitIqfRSqLdqDHNlT5KwT"    # Replace with actual SMB Annual price ID
    }
}

class CreateCheckoutSessionRequest(BaseModel):
    plan_type: Literal["individual", "standard", "smb"]
    billing_interval: Literal["monthly", "annual"]
    quantity: int = 1
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class RetrieveSessionRequest(BaseModel):
    session_id: str

@router.post("/create-checkout-session")
async def create_checkout_session(request: CreateCheckoutSessionRequest):
    try:
        # Default URLs if not provided
        success_url = request.success_url or f"{config["FRONTEND_URL"]}/payment/success"
        cancel_url = request.cancel_url or f"{config["FRONTEND_URL"]}/dashboard/billing"

        # Get the appropriate price ID based on plan type and billing interval
        price_id = PRICE_IDS[request.plan_type][request.billing_interval]

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": request.quantity,
                }
            ],
            mode="subscription",
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=cancel_url,
        )
        return {"sessionId": session.id, "url": session.url}
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid plan type or billing interval")
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return session
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/retrieve-checkout-session")
async def retrieve_checkout_session(request: RetrieveSessionRequest):
    try:
        session = stripe.checkout.Session.retrieve(request.session_id)
        return session  # returns the full session object
    except stripe.error.InvalidRequestError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 

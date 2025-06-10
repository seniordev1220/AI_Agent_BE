from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Literal
import stripe
from ..config import config
from pydantic import BaseModel

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
    seats: int = 1
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class RetrieveSessionRequest(BaseModel):
    session_id: str

@router.post("/create-checkout-session")
async def create_checkout_session(request: CreateCheckoutSessionRequest):
    try:
        # Default URLs if not provided
        success_url = request.success_url or f"{config['FRONTEND_URL']}/payment/success"
        cancel_url = request.cancel_url or f"{config['FRONTEND_URL']}/dashboard/billing"

        # Get the appropriate price IDs based on plan type and billing interval
        price_ids = PRICE_IDS[request.plan_type][request.billing_interval]
        
        # Create line items for base plan and additional seats
        line_items = [
            {
                "price": price_ids["base"],
                "quantity": 1,  # Base plan is always quantity 1
            }
        ]
        
        # Add additional seats if more than 1 seat is requested
        if request.seats > 1:
            line_items.append({
                "price": price_ids["seat"],
                "quantity": request.seats - 1,  # Subtract 1 because base plan includes 1 seat
            })

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
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

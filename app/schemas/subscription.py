from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class PlanType(str, Enum):
    INDIVIDUAL = "individual"
    STANDARD = "standard"
    SMB = "smb"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"

class SubscriptionBase(BaseModel):
    plan_type: PlanType
    seats: Optional[int] = 1

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    seats: Optional[int] = None
    cancel_at_period_end: Optional[bool] = None

class SubscriptionResponse(SubscriptionBase):
    id: int
    status: SubscriptionStatus
    trial_end: Optional[datetime]
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Price configuration for each plan
PLAN_PRICES = {
    PlanType.INDIVIDUAL: {
        "monthly": 39,
        "annual": 351,  # $29/month * 12 with 25% discount
        "base_seats": 1,
        "extra_seat_price": 7
    },
    PlanType.STANDARD: {
        "monthly": 99,
        "annual": 888,  # $74/month * 12 with 25% discount
        "base_seats": 2,
        "extra_seat_price": 7
    },
    PlanType.SMB: {
        "monthly": 157,
        "annual": 1416,  # $118/month * 12 with 25% discount
        "base_seats": 3,
        "extra_seat_price": 5
    }
} 

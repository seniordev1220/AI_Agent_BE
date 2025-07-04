from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal
from datetime import datetime

class PricePlanFeature(BaseModel):
    description: str
    included: bool = True

class PricePlanBase(BaseModel):
    name: str
    monthly_price: Decimal
    annual_price: Decimal
    included_seats: int = 1
    additional_seat_price: Optional[Decimal] = None
    features: Union[List[PricePlanFeature], Dict[str, Any]]  # Support both list and dict
    is_best_value: bool = False
    is_active: bool = True

class PricePlanCreate(PricePlanBase):
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_annual: Optional[str] = None

class PricePlanUpdate(BaseModel):
    name: Optional[str] = None
    monthly_price: Optional[Decimal] = None
    annual_price: Optional[Decimal] = None
    included_seats: Optional[int] = None
    additional_seat_price: Optional[Decimal] = None
    features: Optional[Union[List[PricePlanFeature], Dict[str, Any]]] = None  # Support both list and dict
    is_best_value: Optional[bool] = None
    is_active: Optional[bool] = None
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_annual: Optional[str] = None

class PricePlan(PricePlanBase):
    id: int
    stripe_price_id_monthly: Optional[str]
    stripe_price_id_annual: Optional[str]
    stripe_product_id: Optional[str]
    is_custom: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 

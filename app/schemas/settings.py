from pydantic import BaseModel, EmailStr, HttpUrl, validator
from typing import Optional
from enum import Enum

class AuthSettingsBase(BaseModel):
    email_login_enabled: bool
    sso_enabled: bool
    organization_domain: str | None = None

class AuthSettingsCreate(AuthSettingsBase):
    pass

class AuthSettingsUpdate(AuthSettingsBase):
    email_login_enabled: bool | None = None
    sso_enabled: bool | None = None
    organization_domain: str | None = None

class AuthSettings(AuthSettingsBase):
    id: int

    class Config:
        from_attributes = True

class SubscriptionInterval(str, Enum):
    MONTH = "month"
    YEAR = "year"
    WEEK = "week"
    DAY = "day"

class BrandSettingsBase(BaseModel):
    brand_name: str
    domain: str
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    logo_url: Optional[HttpUrl] = None
    favicon_url: Optional[HttpUrl] = None
    storage_limit_gb: float = 1.0
    max_accounts: int = 5
    subscription_interval: Optional[SubscriptionInterval] = None
    price_amount: Optional[float] = None
    is_active: bool = True

    @validator('primary_color', 'secondary_color')
    def validate_color(cls, v):
        if v and not v.startswith('#'):
            raise ValueError('Color must be a valid hex color starting with #')
        return v

    @validator('storage_limit_gb')
    def validate_storage_limit(cls, v):
        if v <= 0:
            raise ValueError('Storage limit must be greater than 0')
        return v

    @validator('max_accounts')
    def validate_max_accounts(cls, v):
        if v < 1:
            raise ValueError('Maximum accounts must be at least 1')
        return v

    @validator('price_amount')
    def validate_price_amount(cls, v):
        if v is not None and v < 0:
            raise ValueError('Price amount must be greater than or equal to 0')
        return v

class BrandSettingsCreate(BrandSettingsBase):
    pass

class BrandSettingsUpdate(BrandSettingsBase):
    brand_name: Optional[str] = None
    domain: Optional[str] = None

class BrandSettings(BrandSettingsBase):
    id: int
    stripe_price_id: Optional[str] = None

    class Config:
        from_attributes = True 

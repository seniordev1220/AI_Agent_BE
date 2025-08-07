from typing import Optional, List
from pydantic import BaseModel, EmailStr, constr
from enum import Enum
from datetime import datetime

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: str = 'user'

class UserCreate(UserBase):
    password: Optional[str] = None
    provider: Optional[str] = None
    activation_code: Optional[str] = None  # Required for email signup, optional for OAuth

class UserResponse(UserBase):
    id: int
    role: UserRole
    finiite_api_key: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    storage_limit_bytes: Optional[int] = None
    max_users: Optional[int] = None

class UserAdminCreate(UserCreate):
    storage_limit_bytes: Optional[int] = 1073741824  # Default 1GB
    max_users: Optional[int] = 1
    custom_monthly_price: Optional[float] = None
    custom_annual_price: Optional[float] = None

class UserAdminUpdate(UserUpdate):
    custom_monthly_price: Optional[float] = None
    custom_annual_price: Optional[float] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    storage_limit_bytes: int
    storage_used_bytes: int
    max_users: int
    current_users: int
    created_at: datetime
    updated_at: datetime
    finiite_api_key: str
    stripe_customer_id: Optional[str] = None

    class Config:
        from_attributes = True

class User(UserInDB):
    pass

class SubscriptionInfo(BaseModel):
    plan_type: str
    billing_interval: str
    status: str
    stripe_customer_id: Optional[str] = None
    stripe_price_id: Optional[str] = None

    class Config:
        from_attributes = True

class UserWithSubscription(User):
    subscription: Optional[SubscriptionInfo] = None

class UserProfile(UserResponse):
    # Add any additional fields you want to show in profile
    trial_start: Optional[datetime]
    trial_end: Optional[datetime]
    trial_status: Optional[str]

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=6)

class GoogleAuth(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

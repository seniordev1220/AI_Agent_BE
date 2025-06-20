from pydantic import BaseModel, EmailStr, constr
from enum import Enum
from typing import Optional, List
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

class UserResponse(UserBase):
    id: int
    role: UserRole

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

    class Config:
        from_attributes = True

class User(UserInDB):
    pass

class UserWithSubscription(User):
    subscription: Optional[dict] = None

class UserProfile(UserResponse):
    # Add any additional fields you want to show in profile
    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=6)

class GoogleAuth(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

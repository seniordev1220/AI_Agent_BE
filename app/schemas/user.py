from pydantic import BaseModel, EmailStr, constr
from enum import Enum
from typing import Optional

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

class UserCreate(UserBase):
    password: constr(min_length=6)
    role: Optional[UserRole] = UserRole.USER

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
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    role: Optional[UserRole] = None

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

from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

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

class UserProfile(UserResponse):
    # Add any additional fields you want to show in profile
    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

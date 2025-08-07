from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class ActivationCodeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str

class ActivationCodeCreate(ActivationCodeBase):
    pass

class ActivationCodeResponse(BaseModel):
    activation_code: str
    email: EmailStr
    first_name: str
    last_name: str
    created_at: datetime

    class Config:
        from_attributes = True

class ActivationCodeDB(ActivationCodeResponse):
    id: int
    is_used: bool
    used_at: Optional[datetime]
    updated_at: datetime
    hashed_password: str

    class Config:
        from_attributes = True
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional
from enum import Enum

class Provider(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    PERPLEXITY = "perplexity"

class APIKeyBase(BaseModel):
    provider: Provider
    api_key: str

class APIKeyCreate(APIKeyBase):
    pass

class APIKeyUpdate(BaseModel):
    api_key: str

class APIKeyResponse(APIKeyBase):
    id: int
    is_valid: bool
    last_validated: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ModelBase(BaseModel):
    model_name: str
    provider: str
    is_enabled: bool
    logo_path: str

class ModelCreate(ModelBase):
    pass

class ModelUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None

class ModelResponse(ModelBase):
    id: int
    user_id: int
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModelsResponse(BaseModel):
    default_model: str
    models: List[ModelResponse]
    open_sourced_models: List[ModelResponse] 
from datetime import datetime
from pydantic import BaseModel
from typing import List

class ModelBase(BaseModel):
    ai_model_name: str
    provider: str
    is_enabled: bool = False
    is_default: bool = False
    logo_path: str | None = None

class ModelCreate(ModelBase):
    pass

class ModelUpdate(ModelBase):
    pass

class ModelResponse(ModelBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModelsResponse(BaseModel):
    default_model: str
    models: List[ModelResponse]
    open_sourced_models: List[ModelResponse]

    class Config:
        from_attributes = True 
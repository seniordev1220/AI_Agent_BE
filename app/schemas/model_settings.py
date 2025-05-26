from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ModelSettingsBase(BaseModel):
    ai_model_name: str
    provider: str
    is_enabled: bool = False
    is_default: bool = False
    logo_path: str | None = None

class ModelSettingsCreate(ModelSettingsBase):
    pass

class ModelSettings(ModelSettingsBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModelResponse(ModelSettingsBase):
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
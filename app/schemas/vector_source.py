from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class VectorSourceBase(BaseModel):
    name: str
    source_type: str  # Could make this an Enum like your SourceType if desired
    connection_settings: Dict[str, Any]
    embedding_model: str
    table_name: str

class VectorSourceCreate(VectorSourceBase):
    user_id: int

class VectorSourceUpdate(BaseModel):
    name: Optional[str] = None
    connection_settings: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = None

class VectorSourceResponse(VectorSourceBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Allows ORM mode (previously called orm_mode)

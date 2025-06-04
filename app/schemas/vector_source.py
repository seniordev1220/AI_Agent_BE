from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class VectorSourceBase(BaseModel):
    name: str
    source_type: str  # Could make this an Enum like your SourceType if desired
    connection_settings: Dict[str, Any]

class VectorSourceCreate(BaseModel):
    name: str
    source_type: str
    connection_settings: Dict[str, Any]

class VectorSourceUpdate(BaseModel):
    name: Optional[str] = None
    connection_settings: Optional[Dict[str, Any]] = None
    embedding_model: Optional[str] = None

class VectorSourceResponse(VectorSourceBase):
    id: int
    user_id: int
    embedding_model: str
    table_name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Allows ORM mode (previously called orm_mode)

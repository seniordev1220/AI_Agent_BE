from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .vector_source import VectorSourceResponse

# In app/schemas/agent.py
class KnowledgeBaseItem(BaseModel):
    id: int
    name: str
    file_type: str
    file_size: int
    created_at: datetime

    class Config:
        from_attributes = True

class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_private: bool = False
    welcome_message: Optional[str] = None
    instructions: Optional[str] = None
    base_model: str
    category: Optional[str] = None
    reference_enabled: bool = False
    vector_sources_ids: List[int] = []
    avatar_base64: Optional[str] = None

class AgentCreate(AgentBase):
    avatar_url: Optional[str] = None
    vector_source_ids: Optional[List[int]] = None

class AgentUpdate(AgentBase):
    avatar_url: Optional[str] = None
    vector_source_ids: Optional[List[int]] = None

class AgentResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    is_private: bool
    welcome_message: Optional[str] = None
    instructions: Optional[str] = None
    base_model: str
    category: Optional[str] = None
    avatar_base64: Optional[str] = None
    reference_enabled: bool
    vector_sources: List[VectorSourceResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 
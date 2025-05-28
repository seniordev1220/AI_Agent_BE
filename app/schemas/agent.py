from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

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
    avatar_base64: Optional[str] = None

class AgentCreate(AgentBase):
    avatar_url: Optional[str] = None
    knowledge_base_ids: Optional[List[int]] = None  # Changed from List[str] to List[int]

class AgentUpdate(AgentBase):
    avatar_url: Optional[str] = None
    knowledge_base_ids: Optional[List[int]] = None  # Changed from List[str] to List[int]

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
    knowledge_bases: List[KnowledgeBaseItem] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 
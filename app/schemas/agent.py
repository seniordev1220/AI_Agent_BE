from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class KnowledgeBaseItem(BaseModel):
    id: str
    name: str

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
    knowledge_base_ids: Optional[List[str]] = None

class AgentUpdate(AgentBase):
    avatar_url: Optional[str] = None
    knowledge_base_ids: Optional[List[str]] = None

class AgentResponse(AgentBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    knowledge_bases: List[KnowledgeBaseItem] = []

    class Config:
        orm_mode = True 
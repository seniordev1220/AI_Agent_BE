from pydantic import BaseModel
from datetime import datetime
from typing import List

class ChatMessageBase(BaseModel):
    content: str
    model: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessageResponse(ChatMessageBase):
    id: int
    agent_id: int
    user_id: int
    role: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessageResponse]

    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    content: str

class ChatResponse(BaseModel):
    response: str
    sources: List[str] 
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Union, Dict
from enum import Enum

class FileType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    CSV = "csv"
    DOCX = "docx"

class FileReference(BaseModel):
    source_name: str
    content: str
    relevance_score: float

class Attachment(BaseModel):
    name: str
    type: FileType
    url: str  # Base64 or file path
    size: Optional[int] = None

class ChatMessageBase(BaseModel):
    content: str
    model: str
    attachments: Optional[List[Attachment]] = Field(default_factory=list)
    references: Optional[List[FileReference]] = Field(default_factory=list)

class ChatMessageCreate(ChatMessageBase):
    pass

class FileAttachmentResponse(BaseModel):
    id: int
    name: str
    type: str
    url: str
    size: int

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    id: int
    agent_id: int
    user_id: int
    role: str
    content: str
    model: str
    created_at: datetime
    attachments: List[FileAttachmentResponse] = []
    references: List[FileReference] = []
    citations: Optional[List[Union[str, Dict]]] = Field(default_factory=list)
    search_results: Optional[List[Dict]] = Field(default_factory=list)
    choices: Optional[List[Dict]] = Field(default_factory=list)

    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    response: str
    sources: List[str]

class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessageResponse]

    class Config:
        from_attributes = True

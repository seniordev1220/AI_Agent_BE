from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)  # "user" or "assistant"
    content = Column(Text)
    model = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    references = Column(JSON, default=list)  # Store file references from knowledge base

    agent = relationship("Agent", back_populates="messages")
    user = relationship("User", back_populates="messages")
    attachments = relationship("FileAttachment", back_populates="message")
    file_outputs = relationship("FileOutput", back_populates="message")

class FileAttachment(Base):
    __tablename__ = "file_attachments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"))
    name = Column(String)
    type = Column(String)  # File extension/type
    url = Column(String)  # File path or URL
    size = Column(Integer)  # File size in bytes
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("ChatMessage", back_populates="attachments")

class FileOutput(Base):
    __tablename__ = "file_outputs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"))
    name = Column(String)
    type = Column(String)  # File type (csv, pdf, doc, etc.)
    content = Column(Text)  # File content or base64 encoded content
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("ChatMessage", back_populates="file_outputs")

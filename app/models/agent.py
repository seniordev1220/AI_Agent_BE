from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    is_private = Column(Boolean, default=False)
    welcome_message = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    base_model = Column(String)
    category = Column(String, nullable=True)
    avatar_base64 = Column(String)
    reference_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    user = relationship("User", back_populates="agents")
    messages = relationship("ChatMessage", back_populates="agent")
    knowledge_bases = relationship("AgentKnowledgeBase", back_populates="agent")
    
# In app/models/agent.py
class AgentKnowledgeBase(Base):
    __tablename__ = "agent_knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    knowledge_base_id = Column(Integer)  # ID of the selected knowledge base
    name = Column(String, nullable=True)  # Changed to nullable
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    agent = relationship("Agent", back_populates="knowledge_bases") 
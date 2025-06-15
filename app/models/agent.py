from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, Table, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

# Association table for Agent-VectorSource many-to-many relationship
agent_vector_sources = Table(
    'agent_vector_sources',
    Base.metadata,
    Column('agent_id', Integer, ForeignKey('agents.id')),
    Column('vector_source_id', Integer, ForeignKey('vector_sources.id'))
)

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
    vector_sources_ids = Column(ARRAY(Integer), default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Widget-related fields
    greeting = Column(Text, nullable=True)  # Custom greeting message for the widget
    theme = Column(String, default="light")  # Widget theme (light/dark)
    widget_enabled = Column(Boolean, default=True)  # Whether the widget is enabled
    allowed_domains = Column(ARRAY(String), default=[])  # List of domains where the widget can be embedded

    # Relationships
    user = relationship("User", back_populates="agents")
    messages = relationship("ChatMessage", back_populates="agent")
    vector_sources = relationship("VectorSource", secondary=agent_vector_sources, backref="agents") 

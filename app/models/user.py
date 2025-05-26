from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String, nullable=True)  # Make nullable for Google auth
    provider = Column(String, nullable=True)  # Add provider field
    
    # Add relationship to Agent model
    agents = relationship("Agent", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user")
    model_settings = relationship("ModelSettings", back_populates="user")
    data_sources = relationship("DataSource", back_populates="user")

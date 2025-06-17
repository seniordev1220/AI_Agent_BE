from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
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
    role = Column(String, default='user')  # Add role field with default value
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Add relationship to Agent model
    agents = relationship("Agent", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user")
    model_settings = relationship("ModelSettings", back_populates="user")
    data_sources = relationship("DataSource", back_populates="user")
    vector_sources = relationship("VectorSource", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)  # One-to-one relationship
    payments = relationship("Payment", back_populates="user")
    activities = relationship("UserActivity", back_populates="user")  # Add activities relationship

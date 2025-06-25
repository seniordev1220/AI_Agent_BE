from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime

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
    is_superuser = Column(Boolean, default=False)
    finiite_api_key = Column(String, unique=True, index=True)  # Add Finiite API key field
    stripe_customer_id = Column(String, unique=True, nullable=True)  # Add Stripe customer ID field
    
    # Storage and usage limits
    storage_limit_bytes = Column(BigInteger, default=1073741824)  # Default 1GB
    storage_used_bytes = Column(BigInteger, default=0)
    max_users = Column(Integer, default=1)  # Maximum number of users allowed for this account
    current_users = Column(Integer, default=1)  # Current number of users in the account
    
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    trial_status = Column(String, default='free_trial')  # Possible values: free_trial (initial signup), active (after billing), expired
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Brand relationship
    brand_id = Column(Integer, ForeignKey("brand_settings.id"))
    brand = relationship("BrandSettings", back_populates="users")
    
    # Add relationship to Agent model
    agents = relationship("Agent", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user")
    model_settings = relationship("ModelSettings", back_populates="user")
    data_sources = relationship("DataSource", back_populates="user")
    vector_sources = relationship("VectorSource", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)  # One-to-one relationship
    payments = relationship("Payment", back_populates="user")
    activities = relationship("UserActivity", back_populates="user")  # Add activities relationship

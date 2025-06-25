from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, JSON, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class PricePlan(Base):
    __tablename__ = "price_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Individual, Standard, SMB, Custom
    monthly_price = Column(Numeric(10, 2), nullable=False)
    annual_price = Column(Numeric(10, 2), nullable=False)
    included_seats = Column(Integer, default=1)
    additional_seat_price = Column(Numeric(10, 2))
    storage_limit_bytes = Column(BigInteger, default=1073741824)  # Default 1GB
    features = Column(JSON, nullable=False, default=dict)  # Store features as JSON dictionary
    is_best_value = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_custom = Column(Boolean, default=False)  # Flag for custom plans
    stripe_product_id = Column(String, unique=True, nullable=True)  # Stripe product ID
    stripe_price_id_monthly = Column(String, unique=True, nullable=True)  # Monthly price ID
    stripe_price_id_annual = Column(String, unique=True, nullable=True)  # Annual price ID
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="price_plan") 

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class PricePlan(Base):
    __tablename__ = "price_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Individual, Standard, SMB
    monthly_price = Column(Numeric(10, 2), nullable=False)
    annual_price = Column(Numeric(10, 2), nullable=False)
    included_seats = Column(Integer, default=1)
    additional_seat_price = Column(Numeric(10, 2))
    features = Column(JSON, nullable=False)  # Store features as JSON array
    is_best_value = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    stripe_price_id_monthly = Column(String)
    stripe_price_id_annual = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="price_plan") 

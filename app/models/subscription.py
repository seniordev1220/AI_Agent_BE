from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    price_plan_id = Column(Integer, ForeignKey("price_plans.id"))
    stripe_subscription_id = Column(String, unique=True, index=True)
    plan_type = Column(String)  # individual, standard, smb
    billing_interval = Column(String)  # monthly, annual
    seats = Column(Integer, default=1)
    status = Column(String)  # active, canceled, past_due
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription")
    price_plan = relationship("PricePlan", back_populates="subscriptions") 

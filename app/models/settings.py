from sqlalchemy import Column, Integer, String, Boolean, Float, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class SubscriptionInterval(str, enum.Enum):
    MONTH = "month"
    YEAR = "year"
    WEEK = "week"
    DAY = "day"

class AuthSettings(Base):
    __tablename__ = "auth_settings"

    id = Column(Integer, primary_key=True, index=True)
    email_login_enabled = Column(Boolean, default=True)
    sso_enabled = Column(Boolean, default=False)
    organization_domain = Column(String, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "email_login_enabled": self.email_login_enabled,
            "sso_enabled": self.sso_enabled,
            "organization_domain": self.organization_domain
        } 

class BrandSettings(Base):
    __tablename__ = "brand_settings"

    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String, unique=True, index=True)
    domain = Column(String, unique=True)
    
    # Brand colors and assets
    primary_color = Column(String)
    secondary_color = Column(String)
    logo_url = Column(String)  # Store as string
    favicon_url = Column(String)  # Store as string
    
    # Limits
    storage_limit_gb = Column(Float, default=1.0)  # Storage limit in GB
    max_accounts = Column(Integer, default=5)  # Maximum number of accounts
    
    # Pricing
    subscription_interval = Column(String)  # Store as string
    price_amount = Column(Float)  # Price in USD
    stripe_price_id = Column(String)  # Stripe price ID
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="brand") 

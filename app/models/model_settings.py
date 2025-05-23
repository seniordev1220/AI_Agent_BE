from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class ModelSettings(Base):
    __tablename__ = "model_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    model_name = Column(String, index=True)
    provider = Column(String)  # 'openai', 'anthropic', 'google', etc.
    is_enabled = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    logo_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    user = relationship("User", back_populates="model_settings") 
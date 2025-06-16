from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base

class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(String, nullable=False)  # e.g., 'login', 'chat', 'settings_update'
    description = Column(String)
    activity_metadata = Column(JSON, nullable=True)  # Additional activity-specific data
    ip_address = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="activities")

    def __repr__(self):
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, type={self.activity_type})>" 

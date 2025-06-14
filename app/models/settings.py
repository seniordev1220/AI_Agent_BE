from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base

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

from pydantic import BaseModel, EmailStr

class AuthSettingsBase(BaseModel):
    email_login_enabled: bool
    sso_enabled: bool
    organization_domain: str | None = None

class AuthSettingsCreate(AuthSettingsBase):
    pass

class AuthSettingsUpdate(AuthSettingsBase):
    email_login_enabled: bool | None = None
    sso_enabled: bool | None = None
    organization_domain: str | None = None

class AuthSettings(AuthSettingsBase):
    id: int

    class Config:
        from_attributes = True 

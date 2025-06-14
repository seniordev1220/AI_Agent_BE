from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.settings import SettingsService
from app.schemas.settings import AuthSettings, AuthSettingsCreate, AuthSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/auth", response_model=AuthSettings)
def get_auth_settings(db: Session = Depends(get_db)):
    settings = SettingsService.get_auth_settings(db)
    if not settings:
        # Create default settings if none exist
        default_settings = AuthSettingsCreate(
            email_login_enabled=True,
            sso_enabled=False,
            organization_domain=None
        )
        settings = SettingsService.create_auth_settings(db, default_settings)
    return settings

@router.put("/auth/{settings_id}", response_model=AuthSettings)
def update_auth_settings(
    settings_id: int,
    settings: AuthSettingsUpdate,
    db: Session = Depends(get_db)
):
    updated_settings = SettingsService.update_auth_settings(db, settings_id, settings)
    if not updated_settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return updated_settings 

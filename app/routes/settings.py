from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.settings import SettingsService
from app.schemas.settings import AuthSettings, AuthSettingsCreate, AuthSettingsUpdate
from app.utils.activity_logger import log_activity
from ..utils.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/auth", response_model=AuthSettings)
async def get_auth_settings(
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    settings = SettingsService.get_auth_settings(db)
    if not settings:
        # Create default settings if none exist
        default_settings = AuthSettingsCreate(
            email_login_enabled=True,
            sso_enabled=False,
            organization_domain=None
        )
        settings = SettingsService.create_auth_settings(db, default_settings)

        # Log activity for creating default settings
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="settings_create",
            description="Created default authentication settings",
            request=request,
            metadata={
                "settings_id": settings.id,
                "email_login_enabled": settings.email_login_enabled,
                "sso_enabled": settings.sso_enabled,
                "organization_domain": settings.organization_domain
            }
        )

    return settings

@router.put("/auth/{settings_id}", response_model=AuthSettings)
async def update_auth_settings(
    settings_id: int,
    settings: AuthSettingsUpdate,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Get current settings for comparison
    current_settings = SettingsService.get_auth_settings(db)
    if not current_settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    # Store old values for activity log
    old_values = {
        "email_login_enabled": current_settings.email_login_enabled,
        "sso_enabled": current_settings.sso_enabled,
        "organization_domain": current_settings.organization_domain
    }

    # Update settings
    updated_settings = SettingsService.update_auth_settings(db, settings_id, settings)
    if not updated_settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    # Prepare changes for activity log
    changes = {}
    update_data = settings.model_dump(exclude_unset=True)
    for field, new_value in update_data.items():
        if old_values[field] != new_value:
            changes[field] = {
                "old": old_values[field],
                "new": new_value
            }

    # Log activity if there were any changes
    if changes:
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="settings_update",
            description="Updated authentication settings",
            request=request,
            metadata={
                "settings_id": settings_id,
                "changes": changes,
                "current_values": {
                    "email_login_enabled": updated_settings.email_login_enabled,
                    "sso_enabled": updated_settings.sso_enabled,
                    "organization_domain": updated_settings.organization_domain
                }
            }
        )

    return updated_settings 

from sqlalchemy.orm import Session
from app.models.settings import AuthSettings
from app.schemas.settings import AuthSettingsCreate, AuthSettingsUpdate

class SettingsService:
    @staticmethod
    def get_auth_settings(db: Session) -> AuthSettings | None:
        return db.query(AuthSettings).first()

    @staticmethod
    def create_auth_settings(db: Session, settings: AuthSettingsCreate) -> AuthSettings:
        db_settings = AuthSettings(**settings.model_dump())
        db.add(db_settings)
        db.commit()
        db.refresh(db_settings)
        return db_settings

    @staticmethod
    def update_auth_settings(
        db: Session, settings_id: int, settings: AuthSettingsUpdate
    ) -> AuthSettings | None:
        db_settings = db.query(AuthSettings).filter(AuthSettings.id == settings_id).first()
        if not db_settings:
            return None
            
        update_data = settings.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_settings, field, value)
            
        db.commit()
        db.refresh(db_settings)
        return db_settings 

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.settings import SettingsService
from app.schemas.settings import AuthSettings, AuthSettingsCreate, AuthSettingsUpdate
from app.utils.activity_logger import log_activity
from ..utils.auth import get_current_user
from app.models.user import User
from typing import List
from app.models.settings import BrandSettings
from app.schemas.settings import BrandSettingsCreate, BrandSettingsUpdate, BrandSettings as BrandSettingsSchema
from app.utils.auth import get_current_admin_user
import stripe
from app.config import config

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

@router.post("/brands/", response_model=BrandSettingsSchema)
def create_brand(
    brand: BrandSettingsCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Create a new brand (superuser only)"""
    brand_data = brand.dict()
    if brand_data.get('logo_url'):
        brand_data['logo_url'] = str(brand_data['logo_url'])
    if brand_data.get('favicon_url'):
        brand_data['favicon_url'] = str(brand_data['favicon_url'])
    if brand_data.get('subscription_interval'):
        brand_data['subscription_interval'] = brand_data['subscription_interval'].value
    
    db_brand = BrandSettings(**brand_data)
    
    # Create Stripe price if pricing is set
    if brand.subscription_interval and brand.price_amount:
        stripe.api_key = config["STRIPE_SECRET_KEY"]
        product = stripe.Product.create(
            name=f"{brand.brand_name} Subscription"
        )
        
        # Then create a price for that product
        stripe_price = stripe.Price.create(
            unit_amount=int(brand.price_amount * 100),  # Convert to cents
            currency="usd",
            recurring={
                "interval": brand.subscription_interval.value  # Use .value to get the string value
            },
            product=product.id
        )
        db_brand.stripe_price_id = stripe_price.id
    
    
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand

@router.get("/brands/", response_model=List[BrandSettingsSchema])
def list_brands(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """List all brands (superuser only)"""
    return db.query(BrandSettings).all()

@router.get("/brands/{brand_id}", response_model=BrandSettingsSchema)
def get_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Get a specific brand (superuser only)"""
    brand = db.query(BrandSettings).filter(BrandSettings.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@router.put("/brands/{brand_id}", response_model=BrandSettingsSchema)
def update_brand(
    brand_id: int,
    brand_update: BrandSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Update a brand (superuser only)"""
    db_brand = db.query(BrandSettings).filter(BrandSettings.id == brand_id).first()
    if not db_brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    update_data = brand_update.dict(exclude_unset=True)
    
    # Update Stripe price if pricing is changed
    if "subscription_interval" in update_data or "price_amount" in update_data:
        if db_brand.stripe_price_id:
            # Deactivate old price
            stripe.api_key = config["STRIPE_SECRET_KEY"]
            stripe.Price.modify(db_brand.stripe_price_id, active=False)
        
        # Create new price
        if brand_update.subscription_interval and brand_update.price_amount:
            stripe_price = stripe.Price.create(
                unit_amount=int(brand_update.price_amount * 100),
                currency="usd",
                recurring={"interval": brand_update.subscription_interval},
                product_data={"name": f"{db_brand.brand_name} Subscription"}
            )
            update_data["stripe_price_id"] = stripe_price.id
    
    for key, value in update_data.items():
        setattr(db_brand, key, value)
    
    db.commit()
    db.refresh(db_brand)
    return db_brand

@router.delete("/brands/{brand_id}")
def delete_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin_user)
):
    """Delete a brand (superuser only)"""
    db_brand = db.query(BrandSettings).filter(BrandSettings.id == brand_id).first()
    if not db_brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    # Deactivate Stripe price if exists
    if db_brand.stripe_price_id:
        stripe.api_key = config["STRIPE_SECRET_KEY"]
        stripe.Price.modify(db_brand.stripe_price_id, active=False)
    
    db.delete(db_brand)
    db.commit()
    return {"message": "Brand deleted"} 

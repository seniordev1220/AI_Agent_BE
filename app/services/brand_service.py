from sqlalchemy.orm import Session
from app.models.settings import BrandSettings
from app.models.user import User
from fastapi import HTTPException
from app.utils.format_size import get_size_in_gb

class BrandService:
    def __init__(self, db: Session):
        self.db = db

    def check_storage_limit(self, brand_id: int, additional_size_bytes: int = 0) -> bool:
        """Check if adding additional_size_bytes would exceed the brand's storage limit"""
        brand = self.db.query(BrandSettings).filter(BrandSettings.id == brand_id).first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

        # Calculate current storage usage
        # TODO: Implement actual storage calculation based on your storage tracking system
        current_usage_gb = 0  # This should be replaced with actual calculation
        
        # Convert additional size to GB
        additional_size_gb = get_size_in_gb(additional_size_bytes)
        
        # Check if adding new size would exceed limit
        return (current_usage_gb + additional_size_gb) <= brand.storage_limit_gb

    def check_account_limit(self, brand_id: int) -> bool:
        """Check if brand has reached its account limit"""
        brand = self.db.query(BrandSettings).filter(BrandSettings.id == brand_id).first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

        current_accounts = self.db.query(User).filter(User.brand_id == brand_id).count()
        return current_accounts < brand.max_accounts

    def get_brand_usage(self, brand_id: int) -> dict:
        """Get current usage statistics for a brand"""
        brand = self.db.query(BrandSettings).filter(BrandSettings.id == brand_id).first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

        current_accounts = self.db.query(User).filter(User.brand_id == brand_id).count()
        
        # TODO: Implement actual storage calculation
        current_storage_gb = 0  # This should be replaced with actual calculation

        return {
            "storage_usage_gb": current_storage_gb,
            "storage_limit_gb": brand.storage_limit_gb,
            "storage_usage_percentage": (current_storage_gb / brand.storage_limit_gb) * 100 if brand.storage_limit_gb > 0 else 0,
            "account_count": current_accounts,
            "account_limit": brand.max_accounts,
            "account_usage_percentage": (current_accounts / brand.max_accounts) * 100 if brand.max_accounts > 0 else 0
        } 

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.price_plan import PricePlan as PricePlanModel
from ..schemas.price_plan import PricePlan, PricePlanCreate, PricePlanUpdate
from ..utils.auth import get_current_admin_user

router = APIRouter(
    prefix="/price-plans",
    tags=["price_plans"]
)

@router.get("", response_model=List[PricePlan])
def get_price_plans(
    db: Session = Depends(get_db),
    active_only: bool = True
):
    """Get all price plans"""
    query = db.query(PricePlanModel)
    if active_only:
        query = query.filter(PricePlanModel.is_active == True)
    return query.all()

@router.get("/{plan_id}", response_model=PricePlan)
def get_price_plan(
    plan_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific price plan by ID"""
    plan = db.query(PricePlanModel).filter(PricePlanModel.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price plan not found"
        )
    return plan

@router.post("/", response_model=PricePlan)
def create_price_plan(
    plan: PricePlanCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin_user)
):
    """Create a new price plan (admin only)"""
    db_plan = PricePlanModel(**plan.model_dump())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.put("/{plan_id}", response_model=PricePlan)
def update_price_plan(
    plan_id: int,
    plan_update: PricePlanUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin_user)
):
    """Update a price plan (admin only)"""
    db_plan = db.query(PricePlanModel).filter(PricePlanModel.id == plan_id).first()
    if not db_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price plan not found"
        )
    
    for field, value in plan_update.model_dump(exclude_unset=True).items():
        setattr(db_plan, field, value)
    
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_price_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin_user)
):
    """Delete a price plan (admin only)"""
    db_plan = db.query(PricePlanModel).filter(PricePlanModel.id == plan_id).first()
    if not db_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price plan not found"
        )
    
    # Soft delete by setting is_active to False
    db_plan.is_active = False
    db.commit()
    return None 

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Dict
from ..database import get_db
from ..schemas.activation_code import ActivationCodeCreate
from ..services.activation_code_service import ActivationCodeService
from ..utils.activity_logger import log_activity

router = APIRouter(prefix="/activation-codes", tags=["Activation Codes"])

@router.post("", response_model=Dict[str, str])
async def create_activation_code(
    activation_code_data: ActivationCodeCreate,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Create a new activation code or return an existing one if the same user information is provided.
    Returns only the activation code string.
    """
    result = ActivationCodeService.create_activation_code(
        db=db,
        activation_code_data=activation_code_data
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return {"activation_code": result["activation_code"].activation_code}
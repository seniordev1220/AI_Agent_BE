from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User
from ..models.api_key import APIKey
from ..schemas.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse, Provider
from ..utils.auth import get_current_user
from ..utils.api_key_validator import validate_api_key
from ..utils.activity_logger import log_activity
from datetime import datetime

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

@router.post("", response_model=APIKeyResponse)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Check if key already exists for this provider
    existing_key = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.provider == api_key_data.provider
    ).first()
    
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key for {api_key_data.provider} already exists. Please use the update endpoint."
        )

    # Basic format validation based on provider
    await validate_api_key_format(api_key_data.provider, api_key_data.api_key)

    # Validate the API key with provider's API
    try:
        is_valid = await validate_api_key(api_key_data.provider, api_key_data.api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error validating API key: {str(e)}"
        )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid API key for {api_key_data.provider}"
        )

    # Create new API key
    db_api_key = APIKey(
        user_id=current_user.id,
        provider=api_key_data.provider,
        api_key=api_key_data.api_key,
        is_valid=is_valid,
        last_validated=datetime.utcnow()
    )
    
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    
    # Log activity
    await log_activity(
        db=db,
        user_id=current_user.id,
        activity_type="api_key_create",
        description=f"Added API key for {api_key_data.provider}",
        request=request,
        metadata={"provider": api_key_data.provider, "is_valid": is_valid}
    )
    
    return db_api_key

@router.get("", response_model=List[APIKeyResponse])
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(APIKey).filter(APIKey.user_id == current_user.id).all()

@router.put("/{provider}", response_model=APIKeyResponse)
async def update_api_key(
    provider: Provider,
    api_key_data: APIKeyUpdate,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Get existing key
    db_api_key = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.provider == provider
    ).first()
    
    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key for {provider} not found. Please create one first."
        )

    # Don't update if new key is same as old key
    if db_api_key.api_key == api_key_data.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New API key is identical to the current one"
        )

    # Basic format validation based on provider
    await validate_api_key_format(provider, api_key_data.api_key)

    # Validate the new API key
    try:
        is_valid = await validate_api_key(provider, api_key_data.api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error validating API key: {str(e)}"
        )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid API key for {provider}"
        )

    old_key_valid = db_api_key.is_valid
    # Update the key
    db_api_key.api_key = api_key_data.api_key
    db_api_key.is_valid = is_valid
    db_api_key.last_validated = datetime.utcnow()
    
    db.commit()
    db.refresh(db_api_key)
    
    # Log activity
    await log_activity(
        db=db,
        user_id=current_user.id,
        activity_type="api_key_update",
        description=f"Updated API key for {provider}",
        request=request,
        metadata={
            "provider": provider,
            "is_valid": is_valid,
            "previous_key_valid": old_key_valid
        }
    )
    
    return db_api_key

async def validate_api_key_format(provider: Provider, api_key: str):
    """Validate API key format based on provider"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key cannot be empty"
        )

    # Provider-specific format validation
    if provider == Provider.OPENAI:
        # Updated to accept both legacy and new project-based API keys
        if not api_key.startswith(("sk-", "sk-proj-")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OpenAI API key should start with 'sk-' or 'sk-proj-'"
            )
        # Check minimum length for OpenAI keys
        if len(api_key) < 40:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OpenAI API key seems too short"
            )
    elif provider == Provider.ANTHROPIC:
        if not api_key.startswith("sk-ant-api"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Anthropic API key should start with 'sk-ant-api'"
            )
        if len(api_key) < 100:  # Anthropic keys are typically quite long
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Anthropic API key seems too short"
            )
    elif provider == Provider.HUGGINGFACE:
        if not api_key.startswith("hf_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HuggingFace API key should start with 'hf_'"
            )
        if len(api_key) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HuggingFace API key seems too short"
            )
    elif provider == Provider.GEMINI:
        # Google/Gemini API keys can have different formats
        # Remove the strict AIzaSy check
        if len(api_key) < 20:  # Adjust minimum length as needed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gemini API key seems too short"
            )
    elif provider == Provider.DEEPSEEK:
        if not api_key.startswith("sk-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DeepSeek API key should start with 'sk-'"
            )

    # General length check (relaxed for different providers)
    if len(api_key) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key seems too short"
        )
    
    # Check for common invalid characters
    invalid_chars = [' ', '\n', '\t', '\r']
    if any(char in api_key for char in invalid_chars):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key contains invalid characters"
        )

@router.post("/{provider}/validate", response_model=APIKeyResponse)
async def validate_existing_api_key(
    provider: Provider,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get existing key
    db_api_key = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.provider == provider
    ).first()
    
    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key for {provider} not found"
        )

    # Validate the API key
    try:
        is_valid = await validate_api_key(provider, db_api_key.api_key)
    except Exception as e:
        is_valid = False
        db_api_key.is_valid = False
        db_api_key.last_validated = datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error validating API key: {str(e)}"
        )

    # Update validation status
    db_api_key.is_valid = is_valid
    db_api_key.last_validated = datetime.utcnow()
    
    db.commit()
    db.refresh(db_api_key)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key for {provider} is invalid"
        )
    
    return db_api_key

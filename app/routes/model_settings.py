from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User
from ..models.model_settings import ModelSettings
from ..schemas.model_settings import ModelCreate, ModelUpdate, ModelResponse, ModelsResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/models", tags=["Models"])

DEFAULT_MODELS = [
    {"ai_model_name": "GPT-4.5", "provider": "openai", "logo_path": "/model_logo/openai-logo.svg", "is_enabled": False},
    {"ai_model_name": "GPT 3.5 Turbo", "provider": "openai", "logo_path": "/model_logo/gpt4-mini-logo.svg", "is_enabled": False},
    {"ai_model_name": "GPT-4o Mini", "provider": "openai", "logo_path": "/model_logo/gpt4-mini-logo.svg", "is_enabled": True},
    {"ai_model_name": "GPT-4", "provider": "openai", "logo_path": "/model_logo/gpt4-mini-logo.svg", "is_enabled": True},
    {"ai_model_name": "Claude-3.5", "provider": "anthropic", "logo_path": "/model_logo/anthropic-logo.svg", "is_enabled": False},
    {"ai_model_name": "Claude-3.7", "provider": "anthropic", "logo_path": "/model_logo/anthropic-logo.svg", "is_enabled": False},
    {"ai_model_name": "Gemini", "provider": "google", "logo_path": "/model_logo/google-logo.svg", "is_enabled": False},
    {"ai_model_name": "Mistral", "provider": "mistral", "logo_path": "/model_logo/mistral-logo.svg", "is_enabled": False},
]

OPEN_SOURCE_MODELS = [
    {"ai_model_name": "Hugging Face", "provider": "huggingface", "logo_path": "/model_logo/hf-logo.svg", "is_enabled": False},
    {"ai_model_name": "DeepSeek", "provider": "deepseek", "logo_path": "/model_logo/deepseek-logo.svg", "is_enabled": False},
    {"ai_model_name": "Meta: llama. 3.2 1B", "provider": "meta", "logo_path": "/model_logo/meta-logo.svg", "is_enabled": False},
    {"ai_model_name": "Perplexity", "provider": "perplexity", "logo_path": "/model_logo/perplexity-logo.svg", "is_enabled": False},
]

@router.get("", response_model=ModelsResponse)
async def get_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all models and their settings for the current user"""
    
    # Get user's model settings or create default ones if they don't exist
    user_settings = db.query(ModelSettings).filter(
        ModelSettings.user_id == current_user.id
    ).all()

    if not user_settings:
        # Create default settings for the user
        user_settings = []
        for model in DEFAULT_MODELS + OPEN_SOURCE_MODELS:
            setting = ModelSettings(
                user_id=current_user.id,
                ai_model_name=model["ai_model_name"],
                provider=model["provider"],
                is_enabled=model["is_enabled"],
                logo_path=model["logo_path"],
                is_default=model["ai_model_name"] == "Claude-3.7"  # Set default model
            )
            db.add(setting)
            user_settings.append(setting)
        db.commit()
        for setting in user_settings:
            db.refresh(setting)

    # Separate models into regular and open source
    default_model = next(
        (m.ai_model_name for m in user_settings if m.is_default),
        "Claude-3.7"
    )
    
    regular_models = [
        m for m in user_settings 
        if m.ai_model_name in [model["ai_model_name"] for model in DEFAULT_MODELS]
    ]
    
    open_source_models = [
        m for m in user_settings 
        if m.ai_model_name in [model["ai_model_name"] for model in OPEN_SOURCE_MODELS]
    ]

    return ModelsResponse(
        default_model=default_model,
        models=regular_models,
        open_sourced_models=open_source_models
    )

@router.put("/default/{model_name}", response_model=ModelResponse)
async def set_default_model(
    model_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set the default model for the user"""
    
    # Find the model setting
    model_setting = db.query(ModelSettings).filter(
        ModelSettings.user_id == current_user.id,
        ModelSettings.ai_model_name == model_name
    ).first()

    if not model_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )

    # Remove default status from all models
    db.query(ModelSettings).filter(
        ModelSettings.user_id == current_user.id
    ).update({"is_default": False})

    # Set new default model
    model_setting.is_default = True
    db.commit()
    db.refresh(model_setting)

    return model_setting

@router.put("/{model_name}/toggle", response_model=ModelResponse)
async def toggle_model(
    model_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle a model's enabled status"""
    
    model_setting = db.query(ModelSettings).filter(
        ModelSettings.user_id == current_user.id,
        ModelSettings.ai_model_name == model_name
    ).first()

    if not model_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )

    model_setting.is_enabled = not model_setting.is_enabled
    db.commit()
    db.refresh(model_setting)

    return model_setting 
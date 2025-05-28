from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User
from ..models.chat import ChatMessage
from ..models.agent import Agent
from ..models.model_settings import ModelSettings
from ..models.api_key import APIKey
from ..schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from ..utils.auth import get_current_user
from ..utils.ai_client import get_ai_response

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/{agent_id}/messages", response_model=ChatMessageResponse)
async def create_message(
    agent_id: int,
    message: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat message and get AI response"""
    # Check if agent exists and belongs to user
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    # Check if requested model is enabled
    model_setting = db.query(ModelSettings).filter(
        ModelSettings.user_id == current_user.id,
        ModelSettings.ai_model_name == message.model,  # Check requested model
        ModelSettings.is_enabled == True
    ).first()
    if not model_setting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model {message.model} is not enabled or not found"
        )

    # Check API key for the model's provider
    api_key = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.provider == model_setting.provider,
        APIKey.is_valid == True
    ).first()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid API key found for {model_setting.provider}"
        )
    # Save user message
    user_message = ChatMessage(
        agent_id=agent_id,
        user_id=current_user.id,
        role="user",
        content=message.content,
        model=message.model  # Save the model used
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    try:
        # Get chat history
        chat_history = db.query(ChatMessage).filter(
            ChatMessage.agent_id == agent_id,
            ChatMessage.user_id == current_user.id
        ).order_by(ChatMessage.created_at.asc()).all()

        # Prepare conversation context
        conversation = {
            "messages": message.content,
            "agent_instructions": agent.instructions,
            "model": message.model,  # Use requested model
            "provider": model_setting.provider,
            "api_key": api_key.api_key
        }

        # Get AI response
        ai_response = await get_ai_response(conversation)
        # Save AI response
        ai_message = ChatMessage(
            agent_id=agent_id,
            user_id=current_user.id,
            role="assistant",
            content=ai_response,
            model=message.model  # Save the model used
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)

        return ai_message

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting AI response: {str(e)}"
        )

@router.get("/{agent_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history for an agent"""
    messages = db.query(ChatMessage).filter(
        ChatMessage.agent_id == agent_id,
        ChatMessage.user_id == current_user.id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return ChatHistoryResponse(messages=messages)

@router.delete("/{agent_id}/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear chat history for an agent"""
    db.query(ChatMessage).filter(
        ChatMessage.agent_id == agent_id,
        ChatMessage.user_id == current_user.id
    ).delete()
    db.commit() 
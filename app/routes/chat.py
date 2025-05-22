from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User
from ..models.chat import ChatMessage
from ..schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/{agent_id}/messages", response_model=ChatMessageResponse)
async def create_message(
    agent_id: int,
    message: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat message"""
    db_message = ChatMessage(
        agent_id=agent_id,
        user_id=current_user.id,
        role=message.role,
        content=message.content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

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
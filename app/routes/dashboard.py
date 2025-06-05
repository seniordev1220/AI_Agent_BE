from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from typing import List, Dict
from ..database import get_db
from ..models.user import User
from ..models.chat import ChatMessage
from ..models.api_key import APIKey
from ..models.agent import Agent
from ..utils.auth import get_current_user
import tiktoken

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate if tiktoken fails
        return len(text.split()) * 1.3

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics including token usage and top agents"""
    
    # Get total number of users
    total_users = db.query(func.count(User.id)).scalar()
    
    # Get total messages
    total_messages = db.query(func.count(ChatMessage.id)).scalar()
    
    # Calculate token usage across all chat messages
    messages = db.query(ChatMessage.content).all()
    total_tokens = sum(count_tokens(msg[0]) for msg in messages if msg[0])
    
    # Get top AI agents used with message counts
    top_agents = db.query(
        Agent.name,
        func.count(ChatMessage.id).label('message_count')
    ).join(
        ChatMessage, Agent.id == ChatMessage.agent_id
    ).group_by(
        Agent.id, Agent.name
    ).order_by(
        desc('message_count')
    ).limit(3).all()
    
    # Format top agents
    top_agents_list = [
        {
            "name": agent[0],
            "usage_count": agent[1]
        }
        for agent in top_agents
    ]
    
    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "total_tokens": total_tokens,
        "top_agents": top_agents_list
    } 

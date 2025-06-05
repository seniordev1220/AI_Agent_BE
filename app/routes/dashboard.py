from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime, timedelta
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

@router.get("/user-token-usage")
async def get_user_token_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get token usage statistics per user"""
    
    # Query all users and their messages
    user_messages = db.query(
        User.email,
        ChatMessage.content
    ).join(
        ChatMessage, User.id == ChatMessage.user_id
    ).all()
    
    # Calculate token usage per user
    user_tokens = {}
    for email, content in user_messages:
        if content:
            tokens = count_tokens(content)
            user_tokens[email] = user_tokens.get(email, 0) + tokens
    
    # Format response
    token_usage = [
        {
            "email": email,
            "token_usage": tokens
        }
        for email, tokens in sorted(user_tokens.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return token_usage

@router.get("/messages-by-date")
async def get_messages_by_date(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get message count statistics grouped by date"""
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Query message counts grouped by date
    daily_messages = db.query(
        func.date(ChatMessage.created_at).label('date'),
        func.count(ChatMessage.id).label('message_count'),
        User.email
    ).join(
        User, ChatMessage.user_id == User.id
    ).filter(
        ChatMessage.created_at >= start_date,
        ChatMessage.created_at <= end_date
    ).group_by(
        func.date(ChatMessage.created_at),
        User.email
    ).order_by(
        'date'
    ).all()
    
    # Format response
    result = {}
    for date, count, email in daily_messages:
        date_str = date.strftime('%d/%m/%Y')
        if date_str not in result:
            result[date_str] = {}
        result[date_str][email] = count
    
    return {
        "date_range": {
            "start": start_date.strftime('%d/%m/%Y'),
            "end": end_date.strftime('%d/%m/%Y')
        },
        "daily_messages": result
    } 

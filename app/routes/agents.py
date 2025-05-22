from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import base64
import json
from ..database import get_db
from ..models.user import User
from ..models.agent import Agent, AgentKnowledgeBase
from ..schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/agents", tags=["Agents"])

@router.post("", response_model=AgentResponse)
async def create_agent(
    agent_data: str = Form(...),
    avatar: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new agent"""
    try:
        agent_data = AgentCreate(**json.loads(agent_data))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid agent data: {str(e)}"
        )
    
    avatar_base64 = None
    if avatar:
        try:
            contents = await avatar.read()
            avatar_base64 = base64.b64encode(contents).decode('utf-8')
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing avatar: {str(e)}"
            )
    
    db_agent = Agent(
        user_id=current_user.id,
        name=agent_data.name,
        description=agent_data.description,
        is_private=agent_data.is_private,
        welcome_message=agent_data.welcome_message,
        instructions=agent_data.instructions,
        base_model=agent_data.base_model,
        category=agent_data.category,
        avatar_base64=avatar_base64,
        reference_enabled=agent_data.reference_enabled
    )
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)

    if agent_data.knowledge_base_ids:
        for kb_id in agent_data.knowledge_base_ids:
            db.add(AgentKnowledgeBase(
                agent_id=db_agent.id,
                knowledge_base_id=kb_id
            ))
        db.commit()

    return db_agent

@router.get("", response_model=List[AgentResponse])
async def get_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all agents for current user"""
    return db.query(Agent).filter(Agent.user_id == current_user.id).all()

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: str = Form(...),
    avatar: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an agent"""
    try:
        agent_data = AgentUpdate(**json.loads(agent_data))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid agent data: {str(e)}"
        )
    
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if avatar:
        try:
            contents = await avatar.read()
            agent.avatar_base64 = base64.b64encode(contents).decode('utf-8')
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing avatar: {str(e)}"
            )

    for field, value in agent_data.dict(exclude_unset=True).items():
        if field != "knowledge_base_ids":
            setattr(agent, field, value)

    if agent_data.knowledge_base_ids is not None:
        db.query(AgentKnowledgeBase).filter(
            AgentKnowledgeBase.agent_id == agent.id
        ).delete()
        
        for kb_id in agent_data.knowledge_base_ids:
            db.add(AgentKnowledgeBase(
                agent_id=agent.id,
                knowledge_base_id=kb_id
            ))

    db.commit()
    db.refresh(agent)
    return agent

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    db.delete(agent)
    db.commit()
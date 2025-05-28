from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import base64
import json
import os
from pydantic import ValidationError
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
        # Parse directly with Pydantic
        agent_create = AgentCreate(**json.loads(agent_data))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON format in agent_data"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )
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
        name=agent_create.name,
        description=agent_create.description,
        is_private=agent_create.is_private,
        welcome_message=agent_create.welcome_message,
        instructions=agent_create.instructions,
        base_model=agent_create.base_model,
        category=agent_create.category,
        avatar_base64=avatar_base64,
        reference_enabled=agent_create.reference_enabled
    )
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)

    if agent_create.knowledge_base_ids:
        for kb_id in agent_create.knowledge_base_ids:
            db.add(AgentKnowledgeBase(
                agent_id=db_agent.id,
                knowledge_base_id=kb_id
            ))
        db.commit()
        db.refresh(db_agent)

    # Convert SQLAlchemy model to dict and add knowledge_bases
    agent_dict = {
        "id": db_agent.id,
        "user_id": db_agent.user_id,
        "name": db_agent.name,
        "description": db_agent.description,
        "is_private": db_agent.is_private,
        "welcome_message": db_agent.welcome_message,
        "instructions": db_agent.instructions,
        "base_model": db_agent.base_model,
        "category": db_agent.category,
        "avatar_base64": db_agent.avatar_base64,
        "reference_enabled": db_agent.reference_enabled,
        "created_at": db_agent.created_at,
        "updated_at": db_agent.updated_at,
        "knowledge_bases": []
    }

    return agent_dict

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
        agent_update = AgentUpdate(**json.loads(agent_data))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON format in agent_data"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )
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

    for field, value in agent_update.dict(exclude_unset=True).items():
        if field != "knowledge_base_ids":
            setattr(agent, field, value)

    if agent_update.knowledge_base_ids is not None:
        db.query(AgentKnowledgeBase).filter(
            AgentKnowledgeBase.agent_id == agent.id
        ).delete()
        
        for kb_id in agent_update.knowledge_base_ids:
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

@router.post("/{agent_id}/knowledge-bases/upload", response_model=AgentResponse)
async def upload_knowledge_base(
    agent_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a file and create a knowledge base entry for an agent"""
    
    # Check if agent exists and belongs to user
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        # Create directory if it doesn't exist
        upload_dir = f"uploads/agent_{agent_id}/knowledge_bases"
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(upload_dir, file.filename)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Create knowledge base entry
        knowledge_base = AgentKnowledgeBase(
            agent_id=agent_id,
            name=file.filename,
            file_path=file_path,
            file_type=file.content_type,
            file_size=len(contents)
        )
        
        db.add(knowledge_base)
        db.commit()
        db.refresh(agent)

        return agent

    except Exception as e:
        # Clean up file if saved
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )
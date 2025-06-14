from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import base64
import json
import os
from pydantic import ValidationError
from ..database import get_db
from ..models.user import User
from ..models.agent import Agent
from ..models.vector_source import VectorSource
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
        # Parse agent data
        agent_dict = json.loads(agent_data)
        agent_data = AgentCreate(**agent_dict)
        
        # Handle avatar
        avatar_base64 = None
        if avatar:
            contents = await avatar.read()
            avatar_base64 = base64.b64encode(contents).decode('utf-8')
        print(agent_data.vector_source_ids)
        # Create agent
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
            reference_enabled=agent_data.reference_enabled,
            vector_sources_ids=agent_data.vector_source_ids if agent_data.vector_source_ids else []
        )
        
        # Add vector sources if provided
        if agent_data.vector_source_ids:
            vector_sources = db.query(VectorSource).filter(
                VectorSource.id.in_(agent_data.vector_source_ids)
            ).all()
            db_agent.vector_sources.extend(vector_sources)
        
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        
        return db_agent
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

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
    """Get an agent by ID"""
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
    """Update an agent
    
    Args:
        agent_id: The ID of the agent to update
        agent_data: JSON string containing agent update data
        avatar: Optional new avatar file
        current_user: The authenticated user
        db: Database session
        
    Returns:
        Updated agent object
        
    Raises:
        HTTPException: If agent not found or validation fails
    """
    try:
        # Get existing agent with vector sources loaded
        db_agent = db.query(Agent).options(
            joinedload(Agent.vector_sources)
        ).filter(
            Agent.id == agent_id,
            Agent.user_id == current_user.id
        ).first()
        
        if not db_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
            
        # Parse and validate update data
        try:
            agent_dict = json.loads(agent_data)
            agent_update = AgentUpdate(**agent_dict)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in agent_data"
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        
        # Update basic fields
        update_data = agent_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field not in ["vector_source_ids", "avatar_url", "vector_sources_ids"]:
                setattr(db_agent, field, value)
        
        # Handle avatar update
        if avatar:
            try:
                contents = await avatar.read()
                db_agent.avatar_base64 = base64.b64encode(contents).decode('utf-8')
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to process avatar: {str(e)}"
                )
        
        # Update vector sources if provided
        if agent_update.vector_source_ids is not None:
            # Verify all vector sources exist and belong to user
            if agent_update.vector_source_ids:
                vector_sources = db.query(VectorSource).filter(
                    VectorSource.id.in_(agent_update.vector_source_ids),
                    VectorSource.user_id == current_user.id
                ).all()
                
                if len(vector_sources) != len(agent_update.vector_source_ids):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="One or more vector sources not found or not accessible"
                    )
                
                # Clear and update vector sources
                db_agent.vector_sources = vector_sources
            else:
                # Clear vector sources if empty list provided
                db_agent.vector_sources = []
        
        try:
            db.commit()
            db.refresh(db_agent)
            return db_agent
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update agent: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

@router.delete("/{agent_id}")
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

@router.post("/{agent_id}/vector-sources", response_model=AgentResponse)
async def add_vector_source(
    agent_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a file and create a vector source entry for an agent"""
    
    try:
        # Get agent
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.user_id == current_user.id
        ).first()
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        # Create upload directory
        upload_dir = f"uploads/user_{current_user.id}/vector_sources"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_dir, file.filename)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
            
        # Create vector source entry
        vector_source = VectorSource(
            user_id=current_user.id,  # Associate with user instead of agent directly
            name=file.filename,
            source_type="file",  # Add appropriate source type
            connection_settings={"file_path": file_path},  # Store file path in connection settings
            embedding_model="openai",  # Default embedding model
            table_name=f"vector_{current_user.id}_{agent_id}_{file.filename.replace('.', '_').lower()}"
        )
        
        db.add(vector_source)
        db.flush()  # Get the ID without committing
        
        # Associate vector source with agent
        agent.vector_sources.append(vector_source)
        
        db.commit()
        db.refresh(agent)
        
        return agent
        
    except Exception as e:
        db.rollback()
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
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
from ..utils.activity_logger import log_activity
from ..services.trial_service import TrialService
from ..services.subscription_service import SubscriptionService

router = APIRouter(prefix="/agents", tags=["Agents"])

@router.post("", response_model=AgentResponse)
async def create_agent(
    agent_data: str = Form(...),
    avatar: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Create a new agent"""
    try:
        agent_create = AgentCreate.parse_raw(agent_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    # Get existing agents count
    existing_agents_count = db.query(Agent).filter(Agent.user_id == current_user.id).count()
    
    # Special handling for activation code users
    if current_user.trial_status == 'active' and not current_user.subscription:
        if existing_agents_count >= 10:
            raise HTTPException(
                status_code=403,
                detail="You have reached the maximum limit of 10 agents with your activation code."
            )
    # For subscription users
    elif current_user.subscription:
        SubscriptionService.check_agent_limit(db, current_user, existing_agents_count)
    # For trial users
    else:
        TrialService.check_trial_limits(db, current_user, 'agents', existing_agents_count)

    # Handle vector sources if provided
    vector_source_ids = []  # Initialize the variable
    if agent_create.vector_source_ids:
        try:
            # Get all vector sources that belong to the user
            vector_sources = db.query(VectorSource).filter(
                VectorSource.id.in_(agent_create.vector_source_ids),
                VectorSource.user_id == current_user.id
            ).all()

            if len(vector_sources) != len(agent_create.vector_source_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more vector sources not found or not accessible"
                )

            vector_source_ids = [vs.id for vs in vector_sources]

        except Exception as e:
            print(f"Error validating vector sources: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error validating vector sources"
            )

    # Create agent
    db_agent = Agent(
        name=agent_create.name,
        description=agent_create.description,
        instructions=agent_create.instructions,
        user_id=current_user.id,
        vector_sources_ids=vector_source_ids,
        base_model=agent_create.base_model,
        is_private=agent_create.is_private,
        welcome_message=agent_create.welcome_message,
        category=agent_create.category,
        reference_enabled=agent_create.reference_enabled
    )

    # Handle avatar
    if avatar:
        try:
            # Save as base64
            contents = await avatar.read()
            db_agent.avatar_base64 = base64.b64encode(contents).decode('utf-8')
            
            # Also save file in static directory
            static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
            avatars_dir = os.path.join(static_dir, "avatars")
            os.makedirs(avatars_dir, exist_ok=True)

            # Save avatar file and update agent
            avatar_filename = f"{current_user.id}_{db_agent.id}_{avatar.filename}"
            avatar_path = os.path.join(avatars_dir, avatar_filename)
            
            # Seek back to start of file after previous read
            await avatar.seek(0)
            contents = await avatar.read()
            with open(avatar_path, "wb") as f:
                f.write(contents)
            
            db_agent.avatar_url = f"/static/avatars/{avatar_filename}"
            
        except Exception as e:
            print(f"Error saving avatar: {str(e)}")

    # Add to database
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)

    # Set up vector source relationships
    if vector_source_ids:
        try:
            vector_sources = db.query(VectorSource).filter(
                VectorSource.id.in_(vector_source_ids)
            ).all()
            db_agent.vector_sources = vector_sources
            db_agent.vector_sources_ids = vector_source_ids
            db.commit()
            db.refresh(db_agent)
        except Exception as e:
            print(f"Error connecting vector sources: {str(e)}")

    # Log activity
    await log_activity(
        db=db,
        user_id=current_user.id,
        activity_type="agent_create",
        description=f"Created agent: {db_agent.name} ({existing_agents_count + 1}/10)" if current_user.trial_status == 'active' and not current_user.subscription else f"Created agent: {db_agent.name}",
        request=request,
        metadata={
            "agent_id": db_agent.id,
            "agent_name": db_agent.name,
            "vector_sources_count": len(db_agent.vector_sources_ids or []),
            "vector_sources_ids": db_agent.vector_sources_ids,
            "has_avatar": avatar is not None,
            "base_model": db_agent.base_model,
            "current_agent_count": existing_agents_count + 1,
            "max_agents": 10 if current_user.trial_status == 'active' and not current_user.subscription else None
        }
    )

    return db_agent

@router.get("", response_model=List[AgentResponse])
async def get_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all agents for current user"""
    # Get trial status for notification
    trial_status = TrialService.check_trial_status(db, current_user)
    
    # Query agents with default base_model if not set
    agents = db.query(Agent).filter(Agent.user_id == current_user.id).all()
    
    # Set default base_model for any agents that don't have it
    for agent in agents:
        if agent.base_model is None:
            agent.base_model = "gpt-4"  # Set a default model
            db.add(agent)
    
    if agents:
        db.commit()
    
    # If trial is active, add trial status message to response headers
    if not trial_status['has_subscription']:
        # Note: In a real implementation, you would need to modify the response
        # headers or return a custom response object that includes this information
        pass
    
    return agents

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
    
    # Set default base_model if not set
    if agent.base_model is None:
        agent.base_model = "gpt-4"  # Set a default model
        db.add(agent)
        db.commit()
    
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
                # Update vector_sources_ids to match the new vector sources
                db_agent.vector_sources_ids = [vs.id for vs in vector_sources]
            else:
                # Clear vector sources if empty list provided
                db_agent.vector_sources = []
                db_agent.vector_sources_ids = []
        
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
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Delete an agent"""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Store agent info for activity log
    agent_info = {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "vector_sources_count": len(agent.vector_sources_ids or [])
    }
    
    # Delete agent
    db.delete(agent)
    db.commit()

    # Log activity
    await log_activity(
        db=db,
        user_id=current_user.id,
        activity_type="agent_delete",
        description=f"Deleted agent: {agent_info['agent_name']}",
        request=request,
        metadata=agent_info
    )

    return {"message": "Agent deleted successfully"}

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

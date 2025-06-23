from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Dict, Tuple
from urllib.parse import unquote, unquote_plus
import re
from ..database import get_db
from ..models.user import User
from ..models.agent import Agent
from ..schemas.agent import AgentResponse
from ..utils.api_key_validator import validate_finiite_api_key

router = APIRouter(tags=["Embed"])

def extract_path_params(request: Request) -> Tuple[int, str]:
    """
    Extract agent ID and API key from the request path.
    Handles special characters in the API key by using raw URL path.
    """
    try:
        # Get the raw path from the request
        full_path = request.scope.get("raw_path", b"").decode("utf-8")
        if not full_path:
            full_path = request.url.path
        print(f"Raw path: {full_path}")  # Debug log

        # Find the position of 'fk_' in the path
        fk_pos = full_path.find('fk_')
        if fk_pos == -1:
            raise ValueError("API key must start with 'fk_'")

        # Everything after 'fk_' is the API key
        api_key = 'fk_' + full_path[fk_pos + 3:]
        print(f"Raw API key: {api_key}")  # Debug log

        # Get the part before the API key for agent ID
        path_before_key = full_path[:fk_pos].rstrip('/')
        last_slash = path_before_key.rfind('/')
        if last_slash == -1:
            raise ValueError("Invalid URL format")

        # Extract and validate agent ID
        try:
            agent_id = int(path_before_key[last_slash + 1:])
        except ValueError:
            raise ValueError("Invalid agent ID format")

        # URL decode the key to handle special characters
        decoded_key = unquote(api_key)
        print(f"Decoded API key: {decoded_key}")  # Debug log

        return agent_id, decoded_key

    except Exception as e:
        print(f"Error extracting path params: {str(e)}")  # Debug log
        raise ValueError(str(e))

@router.get("/embed/{rest_of_path:path}", response_model=Dict)
@router.get("/{rest_of_path:path}", response_model=Dict)  # Fallback route
async def get_embed_data(
    rest_of_path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get agent and user data for embed widget
    """
    try:
        # Extract agent ID and API key from path
        agent_id, finiite_api_key = extract_path_params(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    print(f"Agent ID: {agent_id}")  # Debug log
    print(f"Final API key: {finiite_api_key}")  # Debug log
    
    # Validate Finiite API key format
    if not await validate_finiite_api_key(finiite_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Finiite API key format: {finiite_api_key}"
        )
    
    # Get user by API key
    user = db.query(User).filter(User.finiite_api_key == finiite_api_key).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get agent and verify ownership
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or access denied"
        )

    # Check if widget is enabled
    if not agent.widget_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Widget is disabled for this agent"
        )

    # Check domain restrictions if any
    if agent.allowed_domains:
        origin = request.headers.get("origin")
        if not origin or not any(domain in origin for domain in agent.allowed_domains):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Domain not allowed for this agent"
            )

    # Return agent and user information
    return {
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "welcome_message": agent.welcome_message,
            "instructions": agent.instructions,
            "base_model": agent.base_model,
            "category": agent.category,
            "avatar_base64": agent.avatar_base64,
            "reference_enabled": agent.reference_enabled,
            "vector_sources_ids": agent.vector_sources_ids,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
            "widget_enabled": agent.widget_enabled,
            "allowed_domains": agent.allowed_domains,
            "is_private": agent.is_private,
            "theme": agent.theme,
            "greeting": agent.greeting,
            "avatar_base64": agent.avatar_base64,
            "reference_enabled": agent.reference_enabled,
            "vector_sources_ids": agent.vector_sources_ids,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        },
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }

@router.get("/embed/widget/{rest_of_path:path}", response_class=HTMLResponse)
@router.get("/widget/{rest_of_path:path}", response_class=HTMLResponse)  # Fallback route
async def get_embed_widget(
    rest_of_path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Return the HTML widget for embedding
    """
    try:
        # Extract agent ID and API key from path
        agent_id, finiite_api_key = extract_path_params(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # First validate the data using the existing endpoint
    data = await get_embed_data(rest_of_path, request, db)
    
    # Return the widget HTML
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Finiite Chat Widget</title>
        <script src="/static/widget.js" defer></script>
        <style>
            body {{
                margin: 0;
                padding: 0;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }}
            #chat-container {{
                flex: 1;
                display: flex;
                flex-direction: column;
            }}
        </style>
    </head>
    <body>
        <div id="chat-container" 
             data-agent-id="{agent_id}" 
             data-api-key="{finiite_api_key}"
             data-theme="{data['agent']['theme']}"
        ></div>
    </body>
    </html>
    """ 

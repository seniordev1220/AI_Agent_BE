from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from ..database import get_db
from ..models.user import User
from ..models.chat import ChatMessage
from ..models.agent import Agent
from ..models.model_settings import ModelSettings
from ..models.api_key import APIKey
from ..schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from ..utils.auth import get_current_user
from ..utils.ai_client import get_ai_response
import os
import uuid
import shutil
from ..models.chat import FileAttachment

router = APIRouter(prefix="/chat", tags=["Chat"])

# Define upload directory and create it if it doesn't exist
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

async def save_uploaded_file(file: UploadFile, user_id: int) -> Dict:
    """Save uploaded file and return metadata"""
    file_ext = file.filename.split(".")[-1].lower()
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_id}.{file_ext}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "name": file.filename,
        "type": file_ext,
        "url": file_path,
        "size": os.path.getsize(file_path)
    }
        

@router.post("/{agent_id}/messages")
async def create_message(
    agent_id: int,
    content: str = Form(...),
    model: str = Form(...),
    stream: Optional[bool] = Form(False),
    files: List[UploadFile] = File(default=[]),
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
        ModelSettings.ai_model_name == model,
        ModelSettings.is_enabled == True
    ).first()
    if not model_setting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model {model} is not enabled or not found"
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
        content=content,
        model=model
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Save file attachments
    file_attachments = []
    for file in files:
        try:
            attachment_data = await save_uploaded_file(file, current_user.id)
            # Create FileAttachment record
            file_attachment = FileAttachment(
                message_id=user_message.id,
                name=attachment_data["name"],
                type=attachment_data["type"],
                url=attachment_data["url"],
                size=attachment_data["size"]
            )
            db.add(file_attachment)
            file_attachments.append(attachment_data)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error saving file: {str(e)}"
            )
    
    db.commit()

    try:
        # Get chat history
        chat_history = db.query(ChatMessage).filter(
            ChatMessage.agent_id == agent_id,
            ChatMessage.user_id == current_user.id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        # Format chat history into messages
        formatted_messages = []
        for msg in chat_history:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Add current message
        formatted_messages.append({
            "role": "user",
            "content": content
        })
        
        # Prepare conversation context
        conversation = {
            "messages": formatted_messages,
            "agent_instructions": agent.instructions,
            "model": model,
            "provider": model_setting.provider,
            "api_key": api_key.api_key,
            "attachments": file_attachments
        }

        if stream:
            # Create a streaming response
            async def response_stream():
                ai_content = []
                async for chunk in await get_ai_response(conversation, stream=True):
                    ai_content.append(chunk)
                    yield f"data: {chunk}\n\n"
                
                # Save the complete message after streaming
                ai_message = ChatMessage(
                    agent_id=agent_id,
                    user_id=current_user.id,
                    role="assistant",
                    content="".join(ai_content),
                    model=model
                )
                db.add(ai_message)
                db.commit()

            return StreamingResponse(
                response_stream(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response (existing code)
            ai_response = await get_ai_response(conversation)
            ai_message = ChatMessage(
                agent_id=agent_id,
                user_id=current_user.id,
                role="assistant",
                content=ai_response,
                model=model
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
    # Query messages with attachments using joinedload
    messages = db.query(ChatMessage).filter(
        ChatMessage.agent_id == agent_id,
        ChatMessage.user_id == current_user.id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Format response with attachments
    formatted_messages = []
    for msg in messages:
        # Query attachments for this message
        attachments = db.query(FileAttachment).filter(
            FileAttachment.message_id == msg.id
        ).all()
        
        formatted_message = {
            "id": msg.id,
            "agent_id": msg.agent_id,
            "user_id": msg.user_id,
            "role": msg.role,
            "content": msg.content,
            "model": msg.model,
            "created_at": msg.created_at,
            "attachments": [{
                "id": att.id,
                "name": att.name,
                "type": att.type,
                "url": att.url,
                "size": att.size
            } for att in attachments]
        }
        formatted_messages.append(formatted_message)
    
    return ChatHistoryResponse(messages=formatted_messages)

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

@router.post("/{agent_id}/generate-image")
async def generate_image(
    agent_id: int,
    prompt: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate an image using OpenAI DALL-E"""
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

    # Check if OpenAI API key exists and is valid
    api_key = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.provider == "openai",
        APIKey.is_valid == True
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid OpenAI API key found"
        )

    try:
        # Save user prompt message first
        user_message = ChatMessage(
            agent_id=agent_id,
            user_id=current_user.id,
            role="user",
            content=f"[Image Generation Request] {prompt}",
            model="dall-e-3"
        )
        db.add(user_message)
        db.commit()

        # Generate image
        from openai import OpenAI
        client = OpenAI(api_key=api_key.api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        # Save the generated image URL as assistant's response
        ai_message = ChatMessage(
            agent_id=agent_id,
            user_id=current_user.id,
            role="assistant",
            content=f"![Generated Image]({response.data[0].url})",
            model="dall-e-3"
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)

        return {
            "message_id": ai_message.id,
            "image_url": response.data[0].url,
            "created_at": ai_message.created_at
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating image: {str(e)}"
        ) 
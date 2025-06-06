from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from ..database import get_db
from ..models.user import User
from ..models.chat import ChatMessage, FileOutput
from ..models.agent import Agent
from ..models.model_settings import ModelSettings
from ..models.api_key import APIKey
from ..models.vector_source import VectorSource
from ..schemas.chat import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from ..utils.auth import get_current_user
from ..utils.ai_client import get_ai_response_from_model, get_ai_response_from_vectorstore
from ..services.vector_service import VectorService
import os
import uuid
import shutil
import json
import base64
import csv
import io
from ..models.chat import FileAttachment
from fpdf import FPDF
from docx import Document

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

    # Get all available vector sources for the user
    available_sources = db.query(VectorSource).filter(
        VectorSource.user_id == current_user.id
    ).all()

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
    openai_api_key = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.provider == "openai",
        APIKey.is_valid == True
    ).first()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid API key found for OpenAI"
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
        
        # Initialize VectorService and search similar content
        vector_service = VectorService(current_user.id)
        
        # Prepare the final response content and references
        response_content = ""
        references = []
        similar_results = []

        # Search through ALL available vector sources
        for vector_source in available_sources:
            try:
                results = await vector_service.search_similar(
                    query=content,
                    source_name=vector_source.table_name,
                    embedding_model=vector_source.embedding_model,
                    api_key=openai_api_key.api_key
                )
                # Add source information to results
                for result in results:
                    result['source_name'] = vector_source.name
                    # Add connection status to the result
                    result['is_connected'] = vector_source.id in (agent.vector_sources_ids or [])
                similar_results.extend(results)
            except Exception as e:
                print(f"Error searching vector source {vector_source.name}: {str(e)}")
                continue

        # Format the response with similar content if results found
        if similar_results:
            # Sort results by relevance score
            similar_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            message_from_vector = ""
            for result in similar_results:
                # Include connection status in the source reference
                connection_status = "" if result['is_connected'] else " (not connected)"
                message_from_vector += f"[From {result['source_name']}{connection_status}]: {result['content']}\n"
                # Store reference
                references.append({
                    "source_name": result['source_name'],
                    "content": result['content'],
                    "relevance_score": result.get('score', 0.0),
                    "is_connected": result['is_connected']
                })
            
            conversation = {
                "messages": message_from_vector,
                "agent_instructions": agent.instructions,
                "model": model,
                "provider": model_setting.provider,
                "api_key": api_key.api_key,
                "attachments": file_attachments,
                "query": content,
                "references": references
            }
            response_content = await get_ai_response_from_vectorstore(conversation)
            
            # Add a note about unconnected sources if any were used
            unconnected_sources = {ref["source_name"] for ref in references if not ref["is_connected"]}
            if unconnected_sources:
                response_content += f"\n\nNote: Some of this information came from sources that aren't connected to me yet: {', '.join(unconnected_sources)}. You may want to connect them for better context in future conversations."
        
        # If no results found in vector search
        if not response_content:
            conversation = {
                "messages": formatted_messages,
                "agent_instructions": agent.instructions,
                "model": model,
                "provider": model_setting.provider,
                "api_key": api_key.api_key,
                "attachments": file_attachments
            }
            response_content = await get_ai_response_from_model(conversation)

        # Check if this is a file generation request
        is_file_request = any(keyword in content.lower() for keyword in ["generate csv", "create csv", "download csv", "generate pdf", "create pdf", "download pdf", "generate doc", "create doc", "download doc"])
        
        if is_file_request:
            # Process file generation request
            file_type = None
            if "csv" in content.lower():
                file_type = "csv"
            elif "pdf" in content.lower():
                file_type = "pdf"
            elif "doc" in content.lower():
                file_type = "doc"
            
            # Get AI response for file content
            if file_type == "pdf":
                agent_instructions = (
                    "Return ONLY the following data as plain text, no explanations, no instructions, no markdown, no code blocks. "
                    "Just output the data, separated by commas, one row per line. For example:\n"
                    "Name,Email,Age,Country\nJohn Doe,johndoe@email.com,30,Canada\nJane Smith,janesmith@email.com,30,Canada\nBob Johnson,bobjohnson@email.com,35,UK"
                )
            elif file_type == "doc":
                agent_instructions = (
                    "Return ONLY the content for a DOC file, no explanations, no code blocks, no markdown, just the plain text."
                )
            else:
                agent_instructions = (
                    "Return ONLY the raw CSV content, no explanations, no code blocks, no markdown, no instructions. "
                    "Just output the CSV data as plain text."
                )
            
            conversation = {
                "messages": formatted_messages,
                "agent_instructions": agent_instructions,
                "model": model,
                "provider": model_setting.provider,
                "api_key": api_key.api_key
            }
            
            file_content = await get_ai_response_from_model(conversation)
            
            # Convert to PDF or DOC if needed
            clean_content = extract_data_only(file_content)
            if file_type == "pdf":
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Arial", size=12)
                for line in clean_content.split('\n'):
                    pdf.cell(0, 10, line, ln=True)
                pdf_bytes = pdf.output(dest='S').encode('latin1')
                file_content_to_save = base64.b64encode(pdf_bytes).decode('utf-8')
            elif file_type == "doc":
                import io
                doc = Document()
                for line in clean_content.split('\n'):
                    doc.add_paragraph(line)
                doc_io = io.BytesIO()
                doc.save(doc_io)
                doc_bytes = doc_io.getvalue()
                file_content_to_save = base64.b64encode(doc_bytes).decode('utf-8')
            else:
                file_content_to_save = clean_content  # CSV stays as plain text
            
            # Create a unique filename
            file_name = f"generated_{uuid.uuid4().hex[:8]}.{file_type}"
            
            # Create FileOutput record
            file_output = FileOutput(
                message_id=user_message.id,
                name=file_name,
                type=file_type,
                content=file_content_to_save
            )
            db.add(file_output)
            db.commit()
            db.refresh(file_output)
            
            # Create assistant message with download link
            response_content = f"I've generated the {file_type.upper()} file for you. You can download it using this link: [Download {file_name}](/download/{file_output.id})"

        ai_message = ChatMessage(
            agent_id=agent_id,
            user_id=current_user.id,
            role="assistant",
            content=response_content,
            model=model,
            references=references
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

@router.post("/{agent_id}/web-search")
async def web_search(
    agent_id: int,
    content: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform web search using Perplexity AI"""
    try:
        import httpx
        import os
        # Save user query message first
        user_message = ChatMessage(
            agent_id=agent_id,
            user_id=current_user.id,
            role="user",
            content=f"[Web Search Query] {content}",
            model="sonar"  # Updated model name
        )
        db.add(user_message)
        db.commit()

        # Get Perplexity API key from environment
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Perplexity API key not configured"
            )

        # Make request to Perplexity API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json={
                    "model": "sonar",
                    "messages": [
                        {"role": "system", "content": "Be precise and concise."},
                        {"role": "user", "content": content}
                    ]
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Perplexity API error: {response.text}"
                )

            result = response.json()
            
            # Format the response content with citations and search results
            ai_content = result["choices"][0]["message"]["content"]

        # Save the enhanced response as assistant's message
        ai_message = ChatMessage(
            agent_id=agent_id,
            user_id=current_user.id,
            role="assistant",
            content=ai_content,
            model="sonar"
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)

        return {
            "message_id": ai_message.id,
            "content": ai_content,
            "created_at": ai_message.created_at,
            "citations": result.get("citations", []),
            "search_results": result.get("search_results", []),
            "choices": result.get("choices", [])
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error performing web search: {str(e)}"
        ) 

@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a generated file"""
    # Get the file output record
    file_output = db.query(FileOutput).filter(FileOutput.id == file_id).first()
    if not file_output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Verify the user has access to this file
    message = db.query(ChatMessage).filter(ChatMessage.id == file_output.message_id).first()
    if not message or message.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    try:
        if file_output.type == "csv":
            # Parse the CSV content and create a file-like object
            content = io.StringIO()
            if file_output.content.startswith("[") and file_output.content.endswith("]"):
                # Handle JSON array format
                rows = json.loads(file_output.content)
                if rows:
                    writer = csv.DictWriter(content, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                # Handle raw CSV content
                content.write(file_output.content)
            
            content.seek(0)
            return StreamingResponse(
                iter([content.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={file_output.name}"}
            )
            
        elif file_output.type in ["pdf", "doc"]:
            try:
                content = base64.b64decode(file_output.content)
                content_io = io.BytesIO(content)
                media_type = "application/pdf" if file_output.type == "pdf" else "application/msword"
                return StreamingResponse(
                    iter([content_io.getvalue()]),
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={file_output.name}"}
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing file content: {str(e)}"
                )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating file: {str(e)}"
        ) 

def extract_data_only(text):
    import re
    # Find the first CSV-like block (header and rows)
    csv_block = None
    # Try to find a markdown code block with CSV data
    match = re.search(r'```[a-zA-Z]*\n([\s\S]*?)```', text)
    if match:
        csv_block = match.group(1).strip()
    else:
        # Fallback: find the first block of lines with commas
        lines = text.splitlines()
        csv_lines = []
        found_header = False
        for line in lines:
            if ',' in line:
                csv_lines.append(line.strip())
                found_header = True
            elif found_header and line.strip() == '':
                break
        csv_block = '\n'.join(csv_lines)
    return csv_block.strip() if csv_block else '' 

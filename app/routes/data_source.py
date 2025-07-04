from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ..database import get_db
from ..models.user import User
from ..models.data_source import DataSource
from ..schemas.data_source import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    SourceType
)
from ..models.vector_source import VectorSource
from ..schemas.vector_source import VectorSourceResponse, VectorSourceCreate
from ..utils.auth import get_current_user
from ..utils.data_source_validator import validate_connection_settings
from ..utils.api_key_validator import validate_finiite_api_key
# from ..services.ingestion_service import IngestionService
# from ..schemas.processed_data import ProcessedDataResponse
from ..utils.file_handler import FileHandler, save_upload_file
from datetime import datetime
import os
from ..services.file_upload_service import FileUploadService
from ..services.size_tracking_service import SizeTrackingService
from ..services.vector_service import VectorService
from ..services.subscription_service import SubscriptionService
from ..services.trial_service import TrialService
from ..config import config
import uuid
from fastapi.responses import StreamingResponse, FileResponse
import mimetypes
from ..utils.activity_logger import log_activity
from google.oauth2 import service_account
from googleapiclient.discovery import build

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])

@router.post("/", response_model=VectorSourceResponse)
async def create_data_source(
    data_source: VectorSourceCreate,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Initialize vector service with only user_id
    vector_service = VectorService(current_user.id)
    
    try:
        # Convert file extensions to comma-separated string if it's a list
        connection_settings = dict(data_source.connection_settings)
        if "file_filter" in connection_settings:
            if isinstance(connection_settings["file_filter"], list):
                # Filter out None values and ensure all items are strings
                valid_extensions = [str(ext) for ext in connection_settings["file_filter"] if ext is not None]
                connection_settings["file_filter"] = ",".join(valid_extensions)
            elif connection_settings["file_filter"] is None:
                # Set a default value if file_filter is None
                connection_settings["file_filter"] = ""
            else:
                # Ensure single extension is a string
                connection_settings["file_filter"] = str(connection_settings["file_filter"])

        # Calculate size before creating the vector source
        size_tracking_service = SizeTrackingService(db)
        size_info = await size_tracking_service.calculate_initial_size(
            data_source.source_type,
            connection_settings
        )
        
        # Check storage limits
        if current_user.subscription:
            # Check subscription limits
            SubscriptionService.check_storage_limit(
                db, 
                current_user, 
                size_info.get("raw_size_bytes", 0)
            )
        else:
            # Check trial limits
            TrialService.check_trial_limits(
                db, 
                current_user, 
                'storage_mb', 
                size_info.get("raw_size_bytes", 0) / (1024 * 1024)  # Convert to MB
            )
        
        # Add size information to connection settings
        connection_settings["file_size"] = size_info.get("raw_size_bytes", 0)
        connection_settings["document_count"] = size_info.get("document_count", 0)

        # Process data source and create vector storage
        db_data_source = await vector_service.create_vector_source(
            name=data_source.name,
            source_type=data_source.source_type,
            connection_settings=connection_settings,
            embedding_model="openai",  # Default to OpenAI
            db=db
        )

        # Track size of the data source
        await size_tracking_service.track_source_size(db_data_source.id)

        # Log activity
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="data_source_create",
            description=f"Created data source: {data_source.name}",
            request=request,
            metadata={
                "data_source_id": db_data_source.id,
                "source_type": data_source.source_type,
                "name": data_source.name
            }
        )

        return db_data_source
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating data source: {str(e)}"
        )

@router.get("", response_model=List[VectorSourceResponse])
async def get_data_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(VectorSource).filter(VectorSource.user_id == current_user.id).all()

@router.get("/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    data_source = db.query(DataSource).filter(
        DataSource.id == data_source_id,
        DataSource.user_id == current_user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    return data_source

@router.put("/{data_source_id}", response_model=DataSourceResponse)
async def update_data_source(
    data_source_id: int,
    data_source_update: DataSourceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    data_source = db.query(DataSource).filter(
        DataSource.id == data_source_id,
        DataSource.user_id == current_user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    if data_source_update.connection_settings:
        validate_connection_settings(data_source.source_type, data_source_update.connection_settings)
        data_source.connection_settings = data_source_update.connection_settings
    
    if data_source_update.name:
        data_source.name = data_source_update.name
    
    db.commit()
    db.refresh(data_source)
    return data_source

@router.delete("/{data_source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    # Initialize vector service with only user_id
    vector_service = VectorService(current_user.id)
    
    # Get data source
    data_source = db.query(DataSource).filter(
        DataSource.id == data_source_id,
        DataSource.user_id == current_user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    try:
        # Delete vector table if it exists
        table_name = f"vector_{current_user.id}_{data_source.name.lower().replace(' ', '_')}"
        await vector_service.vector_db.delete_source_table(table_name)
        
        # Delete physical file if it exists
        if data_source.source_type == "file_upload":
            file_path = data_source.connection_settings.get("file_path")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete data source record
        db.delete(data_source)
        db.commit()
        
        # Store info for activity log
        source_info = {
            "data_source_id": data_source.id,
            "name": data_source.name,
            "source_type": data_source.source_type
        }

        # Log activity
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="data_source_delete",
            description=f"Deleted data source: {source_info['name']}",
            request=request,
            metadata=source_info
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting data source: {str(e)}"
        )

@router.post("/upload", response_model=VectorSourceResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):    
    try:
        # Check file size before processing
        file_size = os.fstat(file.file.fileno()).st_size
        
        # Check file size limit
        if file_size > config["FILE_UPLOAD"]["MAX_SIZE_BYTES"]:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the maximum limit of {config['FILE_UPLOAD']['MAX_SIZE_BYTES'] / (1024 * 1024)}MB"
            )
            
        # Check file type
        if file.content_type not in config["FILE_UPLOAD"]["ALLOWED_TYPES"]:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type {file.content_type} is not supported. Supported types: {', '.join(config['FILE_UPLOAD']['ALLOWED_TYPES'])}"
            )
        
        # Check storage limits
        if current_user.subscription:
            # Check subscription limits
            SubscriptionService.check_storage_limit(db, current_user, file_size)
        else:
            # Check trial limits
            TrialService.check_trial_limits(db, current_user, 'storage_mb', file_size / (1024 * 1024))
        
        file_service = FileUploadService(db)
        data_source = await file_service.process_upload(file, current_user.id)

        # Log activity
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="data_source_upload",
            description=f"Uploaded file: {file.filename}",
            request=request,
            metadata={
                "file_name": file.filename,
                "file_size": file_size,
                "data_source_id": data_source.id,
                "source_type": "file"
            }
        )

        return data_source
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )

@router.post("/{data_source_id}/connection-test", response_model=VectorSourceResponse)
async def test_data_source_connection(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    data_source = db.query(VectorSource).filter(
        VectorSource.id == data_source_id,
        VectorSource.user_id == current_user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    try:
        # Toggle is_converted status
        data_source.is_converted = not data_source.is_converted
        db.commit()
        db.refresh(data_source)
        
        return data_source
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/slack", response_model=VectorSourceResponse)
async def connect_slack(
    file: UploadFile = File(...),
    workspace_url: str = Form(...),
    data_source_name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Initialize file upload service
        file_service = FileUploadService(db)
        
        # Save the ZIP file
        file_uuid = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{file_uuid}{file_extension}"
        file_path = os.path.join(file_service.upload_dir, unique_filename)
        
        # Save file
        await save_upload_file(file, file_path)
        
        # Create connection settings for Slack
        connection_settings = {
            "zip_path": file_path,
            "workspace_url": workspace_url,
            "original_filename": file.filename,
            "content_type": file.content_type,
            "file_size": os.path.getsize(file_path)
        }
        
        # Initialize vector service
        vector_service = VectorService(current_user.id)
        
        # Create vector source for Slack
        data_source = await vector_service.create_vector_source(
            name=data_source_name,
            source_type="slack",
            connection_settings=connection_settings,
            embedding_model="openai",
            db=db
        )
        
        return data_source
        
    except Exception as e:
        # Clean up the file if something goes wrong
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting Slack data source: {str(e)}"
        )

@router.post("/google-drive", response_model=VectorSourceResponse)
async def connect_google_drive(
    data_source_name: str = Form(...),
    file_ids: List[str] = Form(...),
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    try:
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        # Create Drive API service
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Get file metadata and calculate total size
        total_size = 0
        file_metadata = []
        for file_id in file_ids:
            file = drive_service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size",
                supportsAllDrives=True
            ).execute()
            
            # Add size if available, or use exported size for Google Workspace files
            if file.get('size'):
                total_size += int(file.get('size', 0))
            file_metadata.append(file)
        
        # Create connection settings for Google Drive
        connection_settings = {
            "file_ids": file_ids,
            "file_size": total_size,  # Add total size to connection settings
            "file_metadata": file_metadata  # Store metadata for reference
        }
        
        # Initialize vector service
        vector_service = VectorService(current_user.id)
        
        # Create vector source for Google Drive
        data_source = await vector_service.create_vector_source(
            name=data_source_name,
            source_type="google_drive",
            connection_settings=connection_settings,
            embedding_model="openai",
            db=db
        )

        # Log activity
        await log_activity(
            db=db,
            user_id=current_user.id,
            activity_type="data_source_create",
            description=f"Created Google Drive data source: {data_source_name}",
            request=request,
            metadata={
                "data_source_id": data_source.id,
                "source_type": "google_drive",
                "name": data_source_name,
                "file_size": total_size
            }
        )
        
        return data_source
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to Google Drive files: {str(e)}"
        )

@router.post("/hubspot", response_model=VectorSourceResponse)
async def connect_hubspot(
    data_source_name: str = Form(...),
    config: Dict[str, Any] = Form(...),
    stream_name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Initialize vector service
        vector_service = VectorService(current_user.id)
        
        # Prepare connection settings
        connection_settings = {
            "config": config,
            "stream_name": stream_name
        }
        
        # Create vector source
        db_data_source = await vector_service.create_vector_source(
            name=data_source_name,
            source_type="hubspot",
            connection_settings=connection_settings,
            embedding_model="openai",
            db=db
        )
        
        # Track size
        size_tracking_service = SizeTrackingService(db)
        await size_tracking_service.track_source_size(db_data_source.id)
        
        return db_data_source
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to HubSpot: {str(e)}"
        )

@router.post("/salesforce", response_model=VectorSourceResponse)
async def connect_salesforce(
    data_source_name: str = Form(...),
    config: Dict[str, Any] = Form(...),
    stream_name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Initialize vector service
        vector_service = VectorService(current_user.id)
        
        # Prepare connection settings
        connection_settings = {
            "config": config,
            "stream_name": stream_name
        }
        
        # Create vector source
        db_data_source = await vector_service.create_vector_source(
            name=data_source_name,
            source_type="salesforce",
            connection_settings=connection_settings,
            embedding_model="openai",
            db=db
        )
        
        # Track size
        size_tracking_service = SizeTrackingService(db)
        await size_tracking_service.track_source_size(db_data_source.id)
        
        return db_data_source
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to Salesforce: {str(e)}"
        )

@router.get("/{data_source_id}/content")
async def get_data_source_content(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get data source
    data_source = db.query(VectorSource).filter(
        VectorSource.id == data_source_id,
        VectorSource.user_id == current_user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    try:
        # Handle file upload type
        if data_source.source_type == "file_upload":
            file_path = data_source.connection_settings.get("file_path")
            if not file_path or not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
            
            # Get file mime type
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            # Get original filename
            filename = data_source.connection_settings.get("original_filename", os.path.basename(file_path))
            
            # Return file response with inline content disposition for viewing in browser
            return FileResponse(
                file_path,
                media_type=mime_type,
                filename=filename,
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"'
                }
            )
            
        # Handle web scraper type
        elif data_source.source_type == "web_scraper":
            url = data_source.connection_settings.get("urls")
            if not url:
                raise HTTPException(status_code=404, detail="URL not found")
            
            # Return URL for frontend to handle
            return {"url": url}
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Content viewing not supported for source type: {data_source.source_type}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving data source content: {str(e)}"
        )

@router.get("/embed/{data_source_id}/content")
async def get_data_source_content_with_api_key(
    data_source_id: int,
    api_key: str,
    db: Session = Depends(get_db)
):
    """Get data source content using Finiite API key authentication"""
    # Validate Finiite API key
    if not await validate_finiite_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Finiite API key"
        )
    
    # Get user by API key
    user = db.query(User).filter(
        User.finiite_api_key == api_key
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get data source
    data_source = db.query(VectorSource).filter(
        VectorSource.id == data_source_id,
        VectorSource.user_id == user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    try:
        # Handle file upload type
        if data_source.source_type == "file_upload":
            file_path = data_source.connection_settings.get("file_path")
            if not file_path or not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
            
            # Get file mime type
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            # Get original filename
            filename = data_source.connection_settings.get("original_filename", os.path.basename(file_path))
            
            # Return file response with inline content disposition for viewing in browser
            return FileResponse(
                file_path,
                media_type=mime_type,
                filename=filename,
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"'
                }
            )
            
        # Handle web scraper type
        elif data_source.source_type == "web_scraper":
            url = data_source.connection_settings.get("urls")
            if not url:
                raise HTTPException(status_code=404, detail="URL not found")
            
            # Return URL for frontend to handle
            return {"url": url}
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Content viewing not supported for source type: {data_source.source_type}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving data source content: {str(e)}"
        )


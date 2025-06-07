from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
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
# from ..services.ingestion_service import IngestionService
# from ..schemas.processed_data import ProcessedDataResponse
from ..utils.file_handler import FileHandler
from datetime import datetime
import os
from ..services.file_upload_service import FileUploadService
from ..services.size_tracking_service import SizeTrackingService
from ..services.vector_service import VectorService
from ..utils.subscription import check_active_subscription

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])

@router.post("/", response_model=VectorSourceResponse)
async def create_data_source(
    data_source: VectorSourceCreate,
    current_user: User = Depends(get_current_user),
    subscription = Depends(check_active_subscription),
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
    subscription = Depends(check_active_subscription),
    db: Session = Depends(get_db)
):
    return db.query(VectorSource).filter(VectorSource.user_id == current_user.id).all()

@router.get("/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    subscription = Depends(check_active_subscription),
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
    subscription = Depends(check_active_subscription),
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
    subscription = Depends(check_active_subscription),
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
    subscription = Depends(check_active_subscription),
    db: Session = Depends(get_db)
):    
    try:
        file_service = FileUploadService(db)
        data_source = await file_service.process_upload(file, current_user.id)

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
    subscription = Depends(check_active_subscription),
    db: Session = Depends(get_db)
):
    data_source = db.query(VectorSource).filter(
        VectorSource.id == data_source_id,
        VectorSource.user_id == current_user.id
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    try:
        # Toggle is_connected status
        data_source.is_converted = not data_source.is_converted
        db.commit()
        db.refresh(data_source)
        
        return data_source
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

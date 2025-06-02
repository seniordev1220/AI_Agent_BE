from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.user import User
from ..models.data_source import DataSource
from ..schemas.data_source import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    SourceType
)
from ..schemas.vector_source import VectorSourceResponse
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

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])

@router.post("/", response_model=DataSourceResponse)
async def create_data_source(
    data_source: DataSourceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Initialize vector service with only user_id
    vector_service = VectorService(current_user.id)
    
    try:
        # Create data source record
        db_data_source = DataSource(
            user_id=current_user.id,
            name=data_source.name,
            source_type=data_source.source_type,
            connection_settings=data_source.connection_settings
        )
        db.add(db_data_source)
        db.commit()
        db.refresh(db_data_source)

        # Process data source and create vector storage
        await vector_service.create_vector_source(
            name=data_source.name,
            source_type=data_source.source_type,
            connection_settings=data_source.connection_settings,
            embedding_model="openai",  # Default to OpenAI
            db=db
        )

        return db_data_source
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating data source: {str(e)}"
        )

@router.get("", response_model=List[DataSourceResponse])
async def get_data_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(DataSource).filter(DataSource.user_id == current_user.id).all()

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

# @router.post("/{data_source_id}/process", response_model=DataSourceResponse)
# async def process_data_source(
#     data_source_id: int,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     data_source = db.query(DataSource).filter(
#         DataSource.id == data_source_id,
#         DataSource.user_id == current_user.id
#     ).first()
    
#     if not data_source:
#         raise HTTPException(status_code=404, detail="Data source not found")

#     ingestion_service = IngestionService(db)
#     try:
#         processed_source = await ingestion_service.process_data_source(data_source)
#         return processed_source
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/{data_source_id}/processing-history", response_model=List[ProcessedDataResponse])
# async def get_processing_history(
#     data_source_id: int,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     # Verify data source belongs to user
#     data_source = db.query(DataSource).filter(
#         DataSource.id == data_source_id,
#         DataSource.user_id == current_user.id
#     ).first()
    
#     if not data_source:
#         raise HTTPException(status_code=404, detail="Data source not found")

#     # Get processing history
#     processing_history = db.query(ProcessedData).filter(
#         ProcessedData.data_source_id == data_source_id
#     ).order_by(ProcessedData.created_at.desc()).all()
    
#     return processing_history

# @router.get("/{data_source_id}/latest-processing", response_model=ProcessedDataResponse)
# async def get_latest_processing(
#     data_source_id: int,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     # Verify data source belongs to user
#     data_source = db.query(DataSource).filter(
#         DataSource.id == data_source_id,
#         DataSource.user_id == current_user.id
#     ).first()
    
#     if not data_source:
#         raise HTTPException(status_code=404, detail="Data source not found")

#     # Get latest active processing record
#     latest_processing = db.query(ProcessedData).filter(
#         ProcessedData.data_source_id == data_source_id,
#         ProcessedData.is_active == True
#     ).order_by(ProcessedData.last_processed.desc()).first()
    
#     if not latest_processing:
#         raise HTTPException(status_code=404, detail="No processing history found")
    
#     return latest_processing

@router.post("/upload", response_model=VectorSourceResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
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

@router.delete("/upload/{data_source_id}")
async def delete_uploaded_file(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    data_source = db.query(DataSource).filter(
        DataSource.id == data_source_id,
        DataSource.user_id == current_user.id,
        DataSource.source_type == "file_upload"
    ).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    # Delete physical file
    file_path = data_source.connection_settings.get("file_path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    # Delete processed data
    processed_data = db.query(ProcessedData).filter(
        ProcessedData.data_source_id == data_source_id
    ).all()
    for pd in processed_data:
        db.delete(pd)

    # Delete data source
    db.delete(data_source)
    db.commit()

    return {"message": "File and associated data deleted successfully"}

@router.get("/upload/supported-types")
async def get_supported_file_types():
    file_handler = FileHandler()
    return {
        "supported_extensions": file_handler.get_supported_extensions()
    }

@router.post("/{data_source_id}/connection-test", response_model=DataSourceResponse)
async def test_data_source_connection(
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

    try:
        # Toggle is_connected status
        data_source.is_connected = not data_source.is_connected
        db.commit()
        db.refresh(data_source)
        
        return data_source
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

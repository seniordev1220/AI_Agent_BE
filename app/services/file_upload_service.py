from fastapi import UploadFile
import os
import uuid
from datetime import datetime
from ..models.data_source import DataSource
from ..models.processed_data import ProcessedData
from ..utils.langchain_loader import LangChainLoader
from ..utils.file_handler import save_upload_file
from sqlalchemy.orm import Session

class FileUploadService:
    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)

    async def process_upload(self, file: UploadFile, user_id: int) -> DataSource:
        # Generate unique filename
        file_uuid = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{file_uuid}{file_extension}"
        file_path = os.path.join(self.upload_dir, unique_filename)

        # Save file
        await save_upload_file(file, file_path)

        # Create data source record
        data_source = DataSource(
            user_id=user_id,
            name=file.filename,
            source_type="file_upload",
            connection_settings={
                "file_path": file_path,
                "original_filename": file.filename,
                "content_type": file.content_type,
                "file_size": os.path.getsize(file_path)
            }
        )
        
        self.db.add(data_source)
        self.db.commit()
        self.db.refresh(data_source)

        return data_source

    async def cleanup_old_files(self, days: int = 7):
        """Cleanup files older than specified days"""
        from ..utils.file_cleanup import cleanup_old_files
        await cleanup_old_files(self.upload_dir, days) 
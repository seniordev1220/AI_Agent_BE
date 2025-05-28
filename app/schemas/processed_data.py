from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ProcessedDataBase(BaseModel):
    data_source_id: int
    status: str
    processed_size_bytes: int
    total_size_bytes: Optional[int] = None
    chunk_count: int
    total_tokens: Optional[int] = None
    is_active: bool = True

class ProcessedDataCreate(ProcessedDataBase):
    pass

class ProcessedData(ProcessedDataBase):
    id: int
    created_at: datetime
    last_processed: datetime
    vector_store_path: Optional[str]
    document_count: int
    metadata: Dict[str, Any]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ProcessedDataResponse(ProcessedData):
    """Response model for processed data endpoints"""
    pass 
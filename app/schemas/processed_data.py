from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ProcessedDataResponse(BaseModel):
    id: int
    data_source_id: int
    vector_store_path: Optional[str]
    document_count: int
    metadata: Dict[str, Any]
    is_active: bool
    last_processed: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True 
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from app.utils.format_size import format_size

class SourceType(str, Enum):
    AIRTABLE = "airtable"
    DROPBOX = "dropbox"
    GOOGLE_DRIVE = "google_drive"
    SLACK = "slack"
    GITHUB = "github"
    ONE_DRIVE = "one_drive"
    SHAREPOINT = "sharepoint"
    WEB_SCRAPER = "web_scraper"
    SNOWFLAKE = "snowflake"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    FILE_UPLOAD = "file_upload"

class DataSourceBase(BaseModel):
    name: str
    source_type: SourceType
    connection_settings: Dict[str, Any]

class DataSourceCreate(DataSourceBase):
    pass

class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    connection_settings: Optional[Dict[str, Any]] = None

class DataSourceResponse(DataSourceBase):
    id: int
    user_id: int
    raw_size_bytes: int
    processed_size_bytes: int
    total_tokens: int
    document_count: int
    is_connected: bool
    last_sync: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @property
    def total_size_bytes(self) -> int:
        return self.raw_size_bytes + self.processed_size_bytes

    @property
    def raw_size_formatted(self) -> str:
        return format_size(self.raw_size_bytes)

    @property
    def processed_size_formatted(self) -> str:
        return format_size(self.processed_size_bytes)

    @property
    def total_size_formatted(self) -> str:
        return format_size(self.total_size_bytes)

    class Config:
        from_attributes = True 

from ..schemas.data_source import SourceType
from typing import Dict, Any
from fastapi import HTTPException

def validate_connection_settings(source_type: SourceType, settings: Dict[str, Any]):
    validators = {
        SourceType.AIRTABLE: validate_airtable,
        SourceType.DROPBOX: validate_dropbox,
        SourceType.GOOGLE_DRIVE: validate_google_drive,
        SourceType.SLACK: validate_slack,
        SourceType.GITHUB: validate_github,
        SourceType.ONE_DRIVE: validate_one_drive,
        SourceType.SHAREPOINT: validate_sharepoint,
        SourceType.WEB_SCRAPER: validate_web_scraper,
        SourceType.SNOWFLAKE: validate_snowflake,
        SourceType.SALESFORCE: validate_salesforce,
        SourceType.HUBSPOT: validate_hubspot,
        SourceType.FILE_UPLOAD: validate_file_upload
    }
    
    validator = validators.get(source_type)
    if validator:
        validator(settings)

def validate_airtable(settings: Dict[str, Any]):
    required_fields = ["api_token", "table_id", "base_id"]
    _validate_required_fields(required_fields, settings)

def validate_dropbox(settings: Dict[str, Any]):
    required_fields = ["access_token"]
    _validate_required_fields(required_fields, settings)
    
    # Either folder_path or file_paths must be provided
    if not settings.get("folder_path") and not settings.get("file_paths"):
        raise HTTPException(
            status_code=400,
            detail="Either folder_path or file_paths must be provided"
        )

def validate_google_drive(settings: Dict[str, Any]):
    required_fields = ["service_account_key", "token_path"]
    _validate_required_fields(required_fields, settings)

def validate_slack(settings: Dict[str, Any]):
    required_fields = ["zip_path"]
    _validate_required_fields(required_fields, settings)

def validate_github(settings: Dict[str, Any]):
    required_fields = ["repo", "file_filter", "access_token"]
    _validate_required_fields(required_fields, settings)

def validate_one_drive(settings: Dict[str, Any]):
    required_fields = ["drive_id", "auth_config"]
    _validate_required_fields(required_fields, settings)
    
    # Either folder_path or object_ids must be provided
    if not settings.get("folder_path") and not settings.get("object_ids"):
        raise HTTPException(
            status_code=400,
            detail="Either folder_path or object_ids must be provided"
        )

def validate_sharepoint(settings: Dict[str, Any]):
    required_fields = ["tenant_name", "collection_id", "subsite_id"]
    _validate_required_fields(required_fields, settings)

def validate_web_scraper(settings: Dict[str, Any]):
    required_fields = ["urls"]
    _validate_required_fields(required_fields, settings)

def validate_snowflake(settings: Dict[str, Any]):
    required_fields = [
        "query", "user", "password", "account", 
        "warehouse", "role", "database", "schema"
    ]
    _validate_required_fields(required_fields, settings)

def validate_salesforce(settings: Dict[str, Any]):
    required_fields = ["query", "access_token"]
    _validate_required_fields(required_fields, settings)

def validate_hubspot(settings: Dict[str, Any]):
    required_fields = ["access_token", "object_type"]
    _validate_required_fields(required_fields, settings)

def validate_file_upload(settings: Dict[str, Any]):
    required_fields = ["file_path"]
    _validate_required_fields(required_fields, settings)

def _validate_required_fields(required_fields: list, settings: Dict[str, Any]):
    missing_fields = [field for field in required_fields if field not in settings]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing_fields)}"
        ) 

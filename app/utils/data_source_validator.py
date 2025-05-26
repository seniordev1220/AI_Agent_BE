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
        SourceType.SNOWFLAKE: validate_snowflake,
        SourceType.SALESFORCE: validate_salesforce,
        SourceType.HUBSPOT: validate_hubspot,
    }
    
    validator = validators.get(source_type)
    if validator:
        validator(settings)

def validate_airtable(settings: Dict[str, Any]):
    required_fields = ["api_key", "base_id", "table_name"]
    _validate_required_fields(required_fields, settings)

def validate_dropbox(settings: Dict[str, Any]):
    required_fields = ["access_token", "folder_path"]
    _validate_required_fields(required_fields, settings)

def validate_google_drive(settings: Dict[str, Any]):
    required_fields = ["credentials_json", "folder_id"]
    _validate_required_fields(required_fields, settings)

def validate_slack(settings: Dict[str, Any]):
    required_fields = ["bot_token", "channel_ids"]
    _validate_required_fields(required_fields, settings)

def validate_github(settings: Dict[str, Any]):
    required_fields = ["access_token", "repository", "branch"]
    _validate_required_fields(required_fields, settings)

def validate_one_drive(settings: Dict[str, Any]):
    required_fields = ["client_id", "client_secret", "folder_path"]
    _validate_required_fields(required_fields, settings)

def validate_sharepoint(settings: Dict[str, Any]):
    required_fields = ["client_id", "client_secret", "site_url", "folder_path"]
    _validate_required_fields(required_fields, settings)

def validate_snowflake(settings: Dict[str, Any]):
    required_fields = ["account", "username", "password", "warehouse", "database", "schema"]
    _validate_required_fields(required_fields, settings)

def validate_salesforce(settings: Dict[str, Any]):
    required_fields = ["username", "password", "security_token", "domain"]
    _validate_required_fields(required_fields, settings)

def validate_hubspot(settings: Dict[str, Any]):
    required_fields = ["api_key", "portal_id"]
    _validate_required_fields(required_fields, settings)

def _validate_required_fields(required_fields: list, settings: Dict[str, Any]):
    missing_fields = [field for field in required_fields if field not in settings]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing_fields)}"
        ) 
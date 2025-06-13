from typing import Dict, Any, Optional
import os
import json
import aiohttp
from ..models.data_source import DataSource
from ..schemas.data_source import SourceType

class SizeTrackingService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    async def calculate_initial_size(source_type: str, settings: Dict[str, Any]) -> Dict[str, int]:
        """Calculate initial size for different data source types"""
        calculator = SizeCalculatorFactory.get_calculator(source_type)
        return await calculator.calculate_size(settings)

    async def track_source_size(self, source_id: int) -> None:
        """Track the size of a data source"""
        # Get the data source from database
        data_source = self.db.query(DataSource).filter(DataSource.id == source_id).first()
        if not data_source:
            return

        # Calculate size using appropriate calculator
        size_info = await self.calculate_initial_size(
            data_source.source_type,
            data_source.connection_settings
        )

        # Update data source with size information
        data_source.raw_size_bytes = size_info.get("raw_size_bytes", 0)
        data_source.document_count = size_info.get("document_count", 0)
        self.db.commit()

class SizeCalculatorFactory:
    @staticmethod
    def get_calculator(source_type: str):
        calculators = {
            SourceType.FILE_UPLOAD: FileUploadSizeCalculator(),
            SourceType.GITHUB: GitHubSizeCalculator(),
            SourceType.AIRTABLE: AirtableSizeCalculator(),
            SourceType.GOOGLE_DRIVE: GoogleDriveSizeCalculator(),
            SourceType.SLACK: SlackSizeCalculator(),
            SourceType.ONE_DRIVE: OneDriveSizeCalculator(),
            SourceType.SHAREPOINT: SharePointSizeCalculator(),
            SourceType.WEB_SCRAPER: WebScraperSizeCalculator(),
            SourceType.SNOWFLAKE: SnowflakeSizeCalculator(),
            SourceType.SALESFORCE: SalesforceSizeCalculator(),
            SourceType.HUBSPOT: HubspotSizeCalculator(),
        }
        return calculators.get(source_type, DefaultSizeCalculator())

class BaseSizeCalculator:
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        return {
            "raw_size_bytes": 0,
            "document_count": 0
        }

class FileUploadSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        file_path = settings.get("file_path")
        if file_path and os.path.exists(file_path):
            return {
                "raw_size_bytes": os.path.getsize(file_path),
                "document_count": 1
            }
        return await super().calculate_size(settings)

class GitHubSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            repo = settings.get("repo")
            token = settings.get("access_token")
            if not repo or not token:
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with aiohttp.ClientSession() as session:
                # Get repository size
                async with session.get(
                    f"https://api.github.com/repos/{repo}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "raw_size_bytes": data.get("size", 0) * 1024,  # Convert KB to bytes
                            "document_count": 0  # Will be updated after processing
                        }
            
            return await super().calculate_size(settings)
        except Exception:
            return await super().calculate_size(settings)

class AirtableSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            api_key = settings.get("api_key")
            base_id = settings.get("base_id")
            table_name = settings.get("table_name")
            
            if not all([api_key, base_id, table_name]):
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.airtable.com/v0/{base_id}/{table_name}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Estimate size based on JSON response
                        raw_size = len(json.dumps(data).encode('utf-8'))
                        return {
                            "raw_size_bytes": raw_size,
                            "document_count": len(data.get("records", []))
                        }
            
            return await super().calculate_size(settings)
        except Exception:
            return await super().calculate_size(settings)

class DefaultSizeCalculator(BaseSizeCalculator):
    pass 

class GoogleDriveSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            folder_id = settings.get("folder_id")
            credentials = settings.get("credentials_json")
            
            if not all([folder_id, credentials]):
                return await super().calculate_size(settings)

            # Using Google Drive API v3
            url = f"https://www.googleapis.com/drive/v3/files"
            params = {
                "q": f"'{folder_id}' in parents",
                "fields": "files(size,mimeType)"
            }
            headers = {
                "Authorization": f"Bearer {credentials.get('access_token')}",
            }
            
            total_size = 0
            doc_count = 0
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        for file in data.get("files", []):
                            if file.get("size"):
                                total_size += int(file["size"])
                                doc_count += 1
                        
                        return {
                            "raw_size_bytes": total_size,
                            "document_count": doc_count
                        }
            
            return await super().calculate_size(settings)
        except Exception:
            return await super().calculate_size(settings)

class SlackSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            bot_token = settings.get("bot_token")
            channel_ids = settings.get("channel_ids", [])
            
            if not bot_token or not channel_ids:
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json"
            }
            
            total_size = 0
            message_count = 0
            
            async with aiohttp.ClientSession() as session:
                for channel_id in channel_ids:
                    url = "https://slack.com/api/conversations.history"
                    params = {"channel": channel_id, "limit": 100}
                    
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            messages = data.get("messages", [])
                            message_count += len(messages)
                            # Estimate size based on message content
                            for msg in messages:
                                total_size += len(json.dumps(msg).encode('utf-8'))

            return {
                "raw_size_bytes": total_size,
                "document_count": message_count
            }
        except Exception:
            return await super().calculate_size(settings)

class OneDriveSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            client_id = settings.get("client_id")
            access_token = settings.get("access_token")
            folder_path = settings.get("folder_path")
            
            if not all([client_id, access_token, folder_path]):
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            
            url = "https://graph.microsoft.com/v1.0/me/drive/root:/folder_path:/children"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_size = sum(item.get("size", 0) for item in data.get("value", []))
                        doc_count = len(data.get("value", []))
                        return {
                            "raw_size_bytes": total_size,
                            "document_count": doc_count
                        }
            
            return await super().calculate_size(settings)
        except Exception:
            return await super().calculate_size(settings)

class SharePointSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            site_url = settings.get("site_url")
            access_token = settings.get("access_token")
            folder_path = settings.get("folder_path")
            
            if not all([site_url, access_token, folder_path]):
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            
            url = f"{site_url}/_api/web/GetFolderByServerRelativeUrl('{folder_path}')/Files"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_size = sum(item.get("Length", 0) for item in data.get("value", []))
                        doc_count = len(data.get("value", []))
                        return {
                            "raw_size_bytes": total_size,
                            "document_count": doc_count
                        }
            
            return await super().calculate_size(settings)
        except Exception:
            return await super().calculate_size(settings)

class WebScraperSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            urls = settings.get("urls", [])
            if isinstance(urls, str):
                urls = [urls]
            
            if not urls:
                return await super().calculate_size(settings)

            total_size = 0
            doc_count = 0
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    try:
                        async with session.get(url, headers=headers, timeout=30) as response:
                            if response.status == 200:
                                content = await response.text()
                                content_size = len(content.encode('utf-8'))
                                total_size += content_size
                                doc_count += 1
                    except Exception as e:
                        print(f"Error fetching URL {url}: {str(e)}")
                        continue

            # If we couldn't fetch any content successfully, return default
            if doc_count == 0:
                return await super().calculate_size(settings)

            return {
                "raw_size_bytes": total_size,
                "document_count": doc_count
            }
        except Exception as e:
            print(f"Error in WebScraperSizeCalculator: {str(e)}")
            return await super().calculate_size(settings)

class SnowflakeSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            query = settings.get("query")
            connection_string = settings.get("connection_string")
            
            if not all([query, connection_string]):
                return await super().calculate_size(settings)

            # Using Snowflake REST API to get table statistics
            url = f"{connection_string}/queries"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            payload = {
                "sqlText": f"SELECT COUNT(*), OBJECT_AGG('size', TABLE_SIZE) FROM TABLE({query})"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "raw_size_bytes": data.get("size", 0),
                            "document_count": data.get("count", 0)
                        }
            
            return await super().calculate_size(settings)
        except Exception:
            return await super().calculate_size(settings)

class SalesforceSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            access_token = settings.get("access_token")
            instance_url = settings.get("instance_url")
            objects = settings.get("objects", [])
            
            if not all([access_token, instance_url, objects]):
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            total_size = 0
            total_records = 0
            
            async with aiohttp.ClientSession() as session:
                for obj in objects:
                    url = f"{instance_url}/services/data/v52.0/query"
                    params = {"q": f"SELECT COUNT() FROM {obj}"}
                    
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            total_records += data.get("totalSize", 0)
                            # Estimate size based on record count
                            total_size += data.get("totalSize", 0) * 2048  # Estimate 2KB per record

            return {
                "raw_size_bytes": total_size,
                "document_count": total_records
            }
        except Exception:
            return await super().calculate_size(settings)

class HubspotSizeCalculator(BaseSizeCalculator):
    async def calculate_size(self, settings: Dict[str, Any]) -> Dict[str, int]:
        try:
            api_key = settings.get("api_key")
            objects = settings.get("objects", [])
            
            if not api_key or not objects:
                return await super().calculate_size(settings)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            total_size = 0
            total_records = 0
            
            async with aiohttp.ClientSession() as session:
                for obj in objects:
                    url = f"https://api.hubapi.com/crm/v3/objects/{obj}"
                    
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            records = data.get("results", [])
                            total_records += len(records)
                            # Estimate size based on JSON response
                            total_size += len(json.dumps(records).encode('utf-8'))

            return {
                "raw_size_bytes": total_size,
                "document_count": total_records
            }
        except Exception:
            return await super().calculate_size(settings) 

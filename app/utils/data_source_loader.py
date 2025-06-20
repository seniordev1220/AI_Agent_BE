from langchain_community.document_loaders import (
    TextLoader, 
    PyPDFLoader, 
    CSVLoader, 
    UnstructuredExcelLoader,
    AirtableLoader,
    DropboxLoader,
    GoogleDriveLoader,
    SlackDirectoryLoader,
    GithubFileLoader,
    OneDriveLoader,
    SharePointLoader,
    WebBaseLoader,
    SnowflakeLoader,
)
from langchain_community.document_loaders.airbyte import (
    AirbyteSalesforceLoader,
    AirbyteHubspotLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any, Callable
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Dict, Any, Callable, Union

class DataSourceLoader:
    def __init__(self, source_type: str, connection_settings: Dict[str, Any]):
        self.source_type = source_type
        self.connection_settings = connection_settings
            
    async def load_and_split(self) -> List[Dict[str, Any]]:
        documents = await self._load_documents()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)
        return [        
            {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in splits
        ]
            
    def _validate_url(self, url: str) -> str:
        """Validate and format URL to ensure it has a proper scheme."""
        parsed = urlparse(url)
        if not parsed.scheme:
            # If no scheme is provided, prepend https://
            url = f"https://{url}"
            parsed = urlparse(url)
        
        if not parsed.netloc:
            raise ValueError(f"Invalid URL format: {url}")
            
        return url

    async def _load_documents(self):
        if self.source_type == "file_upload":
            return await self._load_file_upload()
        elif self.source_type == "airtable":
            return AirtableLoader(
                api_token=self.connection_settings["api_token"],
                table_id=self.connection_settings["table_id"],
                base_id=self.connection_settings["base_id"]
            ).load()
        elif self.source_type == "dropbox":
            return DropboxLoader(
                dropbox_access_token=self.connection_settings["access_token"],
                dropbox_folder_path=self.connection_settings.get("folder_path"),
                dropbox_file_paths=self.connection_settings.get("file_paths"),
                recursive=self.connection_settings.get("recursive", False)
            ).load()
        elif self.source_type == "google_drive":
            return GoogleDriveLoader(
                folder_id=self.connection_settings.get("folder_id"),
                service_account_key=Path(self.connection_settings["service_account_key"]),
                token_path=Path(self.connection_settings["token_path"]),
                recursive=self.connection_settings.get("recursive", False),
                load_trashed_files=self.connection_settings.get("load_trashed_files", False)
            ).load()
        elif self.source_type == "slack":
            return SlackDirectoryLoader(
                zip_path=self.connection_settings["zip_path"],
                workspace_url=self.connection_settings.get("workspace_url")
            ).load()
        elif self.source_type == "github":
            # Convert string file_filter to callable if provided
            file_filter = None
            if "file_filter" in self.connection_settings:
                filter_pattern = self.connection_settings["file_filter"]
                file_filter = lambda x: filter_pattern in x
                
            return GithubFileLoader(
                repo=self.connection_settings["repo"],
                branch=self.connection_settings.get("branch", "main"),
                file_filter=file_filter,
                github_api_url=self.connection_settings.get("github_api_url", "https://api.github.com"),
                access_token=self.connection_settings["access_token"]
            ).load()
        elif self.source_type == "one_drive":
            return OneDriveLoader(
                drive_id=self.connection_settings["drive_id"],
                folder_path=self.connection_settings.get("folder_path"),
                object_ids=self.connection_settings.get("object_ids"),
                auth_config=self.connection_settings["auth_config"],
                recursive=self.connection_settings.get("recursive", False)
            ).load()
        elif self.source_type == "sharepoint":
            return SharePointLoader(
                tenant_name=self.connection_settings["tenant_name"],
                collection_id=self.connection_settings["collection_id"],
                subsite_id=self.connection_settings["subsite_id"],
                document_library_id=self.connection_settings.get("document_library_id"),
                folder_path=self.connection_settings.get("folder_path"),
                object_ids=self.connection_settings.get("object_ids")
            ).load()
        elif self.source_type == "web_scraper":
            urls = self.connection_settings["urls"]
            if isinstance(urls, str):
                urls = [urls]
            
            # Validate and format all URLs
            validated_urls = []
            total_size = 0
            document_count = 0
            
            for url in urls:
                try:
                    validated_url = self._validate_url(url)
                    validated_urls.append(validated_url)
                except ValueError as e:
                    raise ValueError(f"Invalid URL in web scraper configuration: {str(e)}")
            
            # Load documents and track size
            loader = WebBaseLoader(
                web_paths=validated_urls,
                requests_per_second=self.connection_settings.get("requests_per_second")
            )
            documents = loader.load()
            
            # Calculate size and document count
            for doc in documents:
                total_size += len(doc.page_content.encode('utf-8'))
                document_count += 1
            
            # Update connection settings with size information
            self.connection_settings["file_size"] = total_size
            self.connection_settings["document_count"] = document_count
            
            return documents
        elif self.source_type == "snowflake":
            return SnowflakeLoader(
                query=self.connection_settings["query"],
                user=self.connection_settings["user"],
                password=self.connection_settings["password"],
                account=self.connection_settings["account"],
                warehouse=self.connection_settings["warehouse"],
                role=self.connection_settings["role"],
                database=self.connection_settings["database"],
                schema=self.connection_settings["schema"],
                parameters=self.connection_settings.get("parameters"),
                page_content_columns=self.connection_settings.get("page_content_columns"),
                metadata_columns=self.connection_settings.get("metadata_columns")
            ).load()
        elif self.source_type == "salesforce":
            return AirbyteSalesforceLoader(
                config=self.connection_settings["config"],
                stream_name=self.connection_settings["stream_name"],
                record_handler=self.connection_settings.get("record_handler"),
                state=self.connection_settings.get("state")
            ).load()
        elif self.source_type == "hubspot":
            return AirbyteHubspotLoader(
                config=self.connection_settings["config"],
                stream_name=self.connection_settings["stream_name"],
                record_handler=self.connection_settings.get("record_handler"),
                state=self.connection_settings.get("state")
            ).load()
        else:
            raise ValueError(f"Unsupported source_type: {self.source_type}")

    async def _load_file_upload(self):
        file_path = self.connection_settings["file_path"]
        # Detect by extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            with open(file_path, "r", encoding="utf-8") as temp_file:
                loader = PyPDFLoader(temp_file.name)
        elif ext == ".csv":
            loader = CSVLoader(file_path=file_path)
        elif ext in [".xls", ".xlsx"]:
            loader = UnstructuredExcelLoader(file_path=file_path)
        elif ext == ".txt":
            loader = TextLoader(file_path=file_path)
        else:
            raise ValueError(f"Unsupported uploaded file extension: {ext}")
        
        return loader.load()
  
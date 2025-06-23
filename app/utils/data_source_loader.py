from langchain_community.document_loaders import (
    TextLoader, 
    PyPDFLoader, 
    CSVLoader, 
    UnstructuredExcelLoader,
    AirtableLoader,
    DropboxLoader,
    SlackDirectoryLoader,
    GithubFileLoader,
    OneDriveLoader,
    SharePointLoader,
    WebBaseLoader,
    SnowflakeLoader,
)
from langchain_google_community import GoogleDriveLoader
from langchain_community.document_loaders.airbyte import (
    AirbyteSalesforceLoader,
    AirbyteHubspotLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from typing import List, Dict, Any, Callable, Union
import os
import json
from pathlib import Path
from urllib.parse import urlparse
from ..config import config
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import io
from googleapiclient.http import MediaIoBaseDownload

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
            # Debug: Print environment variables
            print("GOOGLE_APPLICATION_CREDENTIALS:", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
            print("Service account file exists:", os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")))
            
            try:
                # Load service account credentials
                credentials = service_account.Credentials.from_service_account_file(
                    os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
                    scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
                
                # Print service account email and project details
                print(f"Service Account Email: {credentials.service_account_email}")
                print(f"Project ID: {credentials.project_id}")
                
                # Get file IDs from the connection settings
                file_ids = self.connection_settings.get("file_ids", [])
                
                # Convert sharing URLs to file IDs if needed
                processed_file_ids = []
                for file_id in file_ids:
                    if isinstance(file_id, str):  # Ensure file_id is a string
                        if "drive.google.com" in file_id:
                            # Extract file ID from sharing URL
                            if "/file/d/" in file_id:
                                # Format: https://drive.google.com/file/d/FILE_ID/view
                                file_id = file_id.split("/file/d/")[1].split("/")[0]
                            elif "id=" in file_id:
                                # Format: https://drive.google.com/open?id=FILE_ID
                                file_id = file_id.split("id=")[1].split("&")[0]
                        processed_file_ids.append(file_id)
                
                print(f"Processing file IDs: {processed_file_ids}")
                
                # Create Drive API service
                drive_service = build('drive', 'v3', credentials=credentials)
                
                # List files to verify API access
                print("Attempting to list files to verify API access...")
                files_list = drive_service.files().list(pageSize=1).execute()
                print(f"API access verified. Can list files: {bool(files_list)}")
                
                # Process each file
                all_documents = []
                for file_id in processed_file_ids:
                    try:
                        print(f"\nAttempting to access file {file_id}...")
                        file = drive_service.files().get(
                            fileId=file_id,
                            fields="id, name, mimeType, size",
                            supportsAllDrives=True
                        ).execute()
                        
                        print(f"Successfully accessed file metadata:")
                        print(f"- Name: {file.get('name')}")
                        print(f"- Type: {file.get('mimeType')}")
                        print(f"- Size: {file.get('size', '0')} bytes")
                        
                        # Check if file is empty
                        if file.get('size', '0') == '0':
                            raise Exception(f"File '{file.get('name')}' is empty (0 bytes). Please make sure the file has content before processing.")
                        
                        mime_type = file.get('mimeType', '')
                        
                        # Handle Google Workspace files
                        if mime_type.startswith('application/vnd.google-apps.'):
                            # Create docs service for Google Workspace files
                            docs_service = None
                            export_mime_type = None
                            
                            if mime_type == 'application/vnd.google-apps.document':
                                docs_service = build('docs', 'v1', credentials=credentials)
                                export_mime_type = 'text/plain'
                            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                                docs_service = build('sheets', 'v4', credentials=credentials)
                                export_mime_type = 'text/csv'
                            elif mime_type == 'application/vnd.google-apps.presentation':
                                docs_service = build('slides', 'v1', credentials=credentials)
                                # Try PDF first for presentations to preserve more content
                                export_mime_type = 'application/pdf'
                            
                            if export_mime_type:
                                print(f"Exporting Google Workspace file as {export_mime_type}")
                                try:
                                    request = drive_service.files().export_media(
                                        fileId=file_id,
                                        mimeType=export_mime_type
                                    )
                                    fh = io.BytesIO()
                                    downloader = MediaIoBaseDownload(fh, request)
                                    done = False
                                    while done is False:
                                        status, done = downloader.next_chunk()
                                        if status:
                                            print(f"Download {int(status.progress() * 100)}%")
                                    
                                    # Check if we got any content
                                    content = fh.getvalue()
                                    if not content:
                                        raise Exception(f"Exported file is empty. Please make sure the document contains content.")
                                    
                                    # For PDF exports of presentations, try to extract text
                                    if export_mime_type == 'application/pdf':
                                        from PyPDF2 import PdfReader
                                        from io import BytesIO
                                        
                                        pdf = PdfReader(BytesIO(content))
                                        text_content = []
                                        for page in pdf.pages:
                                            text_content.append(page.extract_text())
                                        content = '\n'.join(text_content).encode('utf-8')
                                    
                                    # Create a document from the exported content
                                    content = content.decode('utf-8')
                                    if not content.strip():
                                        raise Exception(f"Exported file contains no text content. Please make sure the document has readable text.")
                                        
                                    metadata = {
                                        "source": f"google_drive/{file.get('name')}",
                                        "file_id": file_id,
                                        "mime_type": mime_type,
                                        "file_name": file.get('name')
                                    }
                                    document = Document(
                                        page_content=content,
                                        metadata=metadata
                                    )
                                    all_documents.append(document)
                                    print(f"Successfully processed Google Workspace file: {file.get('name')}")
                                except Exception as e:
                                    print(f"Error exporting file {file.get('name')}: {str(e)}")
                                    # If PDF export fails for presentations, try plain text
                                    if export_mime_type == 'application/pdf':
                                        print("Retrying with plain text export...")
                                        export_mime_type = 'text/plain'
                                        request = drive_service.files().export_media(
                                            fileId=file_id,
                                            mimeType=export_mime_type
                                        )
                                        fh = io.BytesIO()
                                        downloader = MediaIoBaseDownload(fh, request)
                                        done = False
                                        while done is False:
                                            status, done = downloader.next_chunk()
                                            if status:
                                                print(f"Download {int(status.progress() * 100)}%")
                                        content = fh.getvalue().decode('utf-8')
                                        if not content.strip():
                                            raise Exception(f"Exported file contains no text content. Please make sure the document has readable text.")
                                        metadata = {
                                            "source": f"google_drive/{file.get('name')}",
                                            "file_id": file_id,
                                            "mime_type": mime_type,
                                            "file_name": file.get('name')
                                        }
                                        document = Document(
                                            page_content=content,
                                            metadata=metadata
                                        )
                                        all_documents.append(document)
                                        print(f"Successfully processed Google Workspace file as plain text: {file.get('name')}")
                                    else:
                                        raise
                            else:
                                print(f"Unsupported Google Workspace file type: {mime_type}")
                        else:
                            # For non-Google Workspace files, use the standard loader
                            loader = GoogleDriveLoader(
                                file_ids=[file_id],
                                credentials=credentials,
                                service_account_key=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                            )
                            documents = loader.load()
                            all_documents.extend(documents)
                            print(f"Successfully processed file: {file.get('name')}")
                            
                    except Exception as e:
                        print(f"Error processing file {file_id}: {str(e)}")
                        raise
                
                return all_documents
                    
            except Exception as e:
                print(f"Error loading Google Drive documents: {str(e)}")
                raise
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
  
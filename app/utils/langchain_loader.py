from langchain_community.document_loaders import (
    AirtableLoader,
    GoogleDriveLoader,
    SlackDirectoryLoader,
    SnowflakeLoader,
    WebBaseLoader,
    UnstructuredFileLoader,
    PDFMinerLoader,
    TextLoader,
    CSVLoader,
    GitLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List, Dict, Any
from ..models.data_source import DataSource
from ..schemas.data_source import SourceType
import tempfile
import os
import mimetypes

class LangChainLoader:
    def __init__(self, data_source: DataSource):
        self.data_source = data_source
        self.settings = data_source.connection_settings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

    async def load_and_split(self) -> List[Any]:
        loader = self._get_loader()
        documents = loader.load()
        return self.text_splitter.split_documents(documents)

    def _get_loader(self):
        loader_map = {
            SourceType.AIRTABLE: self._load_airtable,
            SourceType.GITHUB: self._load_github,
            SourceType.GOOGLE_DRIVE: self._load_google_drive,
            SourceType.SLACK: self._load_slack,
            SourceType.SNOWFLAKE: self._load_snowflake,
            SourceType.WEB_SCRAPER: self._load_web,
            SourceType.FILE_UPLOAD: self._load_file
        }

        loader_func = loader_map.get(self.data_source.source_type)
        if not loader_func:
            raise ValueError(f"Unsupported source type: {self.data_source.source_type}")
        
        return loader_func()

    def _load_airtable(self):
        return AirtableLoader(
            api_key=self.settings["api_key"],
            base_id=self.settings["base_id"],
            table_name=self.settings["table_name"]
        )

    def _load_github(self):
        return GitLoader(
            repo=self.settings["repository"],
            branch=self.settings["branch"],
            access_token=self.settings["access_token"]
        )

    def _load_google_drive(self):
        return GoogleDriveLoader(
            credentials_path=self._save_temp_credentials(),
            folder_id=self.settings["folder_id"]
        )

    def _load_slack(self):
        return SlackDirectoryLoader(
            slack_token=self.settings["bot_token"],
            channel_ids=self.settings["channel_ids"]
        )

    def _load_snowflake(self):
        return SnowflakeLoader(
            query=self.settings.get("query", "SELECT * FROM your_table"),
            connection_string=self._get_snowflake_connection_string()
        )

    def _load_web(self):
        return WebBaseLoader(self.settings["urls"])

    def _load_file(self):
        file_path = self.settings["file_path"]
        file_type = mimetypes.guess_type(file_path)[0]

        loader_map = {
            'application/pdf': PDFMinerLoader,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocxLoader,
            'text/plain': TextLoader,
            'text/csv': CSVLoader,
        }

        loader_class = loader_map.get(file_type, UnstructuredFileLoader)
        return loader_class(file_path)

    def _save_temp_credentials(self) -> str:
        """Save credentials JSON to temporary file and return path."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(self.settings["credentials_json"], f)
            return f.name

    def _get_snowflake_connection_string(self) -> str:
        return f"snowflake://{self.settings['username']}:{self.settings['password']}@" \
               f"{self.settings['account']}/{self.settings['database']}/" \
               f"{self.settings['schema']}?warehouse={self.settings['warehouse']}"

    async def process_uploaded_file(self, file_path: str) -> List[Any]:
        self.settings["file_path"] = file_path
        return await self.load_and_split()

class VectorStoreManager:
    def __init__(self, openai_api_key: str):
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
        self.persist_directory = "db/vectorstore"

    async def create_or_update(self, documents: List[Any], source_id: str):
        vectorstore = Chroma(
            persist_directory=f"{self.persist_directory}/{source_id}",
            embedding_function=self.embeddings
        )
        
        # Add documents to vector store
        vectorstore.add_documents(documents)
        return vectorstore

    async def get_vectorstore(self, source_id: str):
        return Chroma(
            persist_directory=f"{self.persist_directory}/{source_id}",
            embedding_function=self.embeddings
        ) 
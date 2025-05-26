from ..utils.langchain_loader import LangChainLoader, VectorStoreManager
from ..models.data_source import DataSource
from ..models.processed_data import ProcessedData
from ..models.api_key import APIKey
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any
import tiktoken
import os

class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    async def process_data_source(self, data_source: DataSource):
        # Get OpenAI API key for embeddings
        api_key = self.db.query(APIKey).filter(
            APIKey.user_id == data_source.user_id,
            APIKey.provider == "openai",
            APIKey.is_valid == True
        ).first()

        if not api_key:
            raise ValueError("Valid OpenAI API key required for embeddings")

        try:
            # Initialize loaders
            loader = LangChainLoader(data_source)
            vector_store_manager = VectorStoreManager(api_key.api_key)

            # Load and split documents
            documents = await loader.load_and_split()

            # Calculate sizes and tokens
            size_info = await self._calculate_size_info(data_source, documents)

            # Create or update vector store
            vector_store_path = f"datasource_{data_source.id}"
            vectorstore = await vector_store_manager.create_or_update(
                documents,
                vector_store_path
            )

            # Calculate vector store size
            vector_store_size = await self._calculate_vector_store_size(vector_store_path)
            size_info['vector_store_size'] = vector_store_size
            size_info['total_size'] += vector_store_size

            # Create or update processed data record
            processed_data = self.db.query(ProcessedData).filter(
                ProcessedData.data_source_id == data_source.id,
                ProcessedData.is_active == True
            ).first()

            if processed_data:
                processed_data.document_count = len(documents)
                processed_data.total_tokens = size_info['total_tokens']
                processed_data.total_size_bytes = size_info['total_size']
                processed_data.last_processed = datetime.utcnow()
                processed_data.metadata = {
                    **size_info,
                    "chunk_size": loader.text_splitter.chunk_size,
                    "chunk_overlap": loader.text_splitter.chunk_overlap,
                    "source_type": data_source.source_type,
                    "processing_status": "success"
                }
            else:
                processed_data = ProcessedData(
                    data_source_id=data_source.id,
                    vector_store_path=vector_store_path,
                    document_count=len(documents),
                    total_tokens=size_info['total_tokens'],
                    total_size_bytes=size_info['total_size'],
                    metadata={
                        **size_info,
                        "chunk_size": loader.text_splitter.chunk_size,
                        "chunk_overlap": loader.text_splitter.chunk_overlap,
                        "source_type": data_source.source_type,
                        "processing_status": "success"
                    }
                )
                self.db.add(processed_data)

            # Update data source status
            data_source.last_sync = datetime.utcnow()
            data_source.is_connected = True

            # Update size information after processing
            processed_size = await self._calculate_processed_size(vector_store_path)
            
            data_source.processed_size_bytes = processed_size
            data_source.total_tokens = processed_data.total_tokens  # From tokenizer
            data_source.document_count = len(documents)
            
            self.db.commit()
            return data_source

        except Exception as e:
            # Log the error and create a failed processing record
            error_metadata = {
                "error": str(e),
                "source_type": data_source.source_type,
                "processing_status": "failed"
            }
            
            failed_process = ProcessedData(
                data_source_id=data_source.id,
                document_count=0,
                total_tokens=0,
                total_size_bytes=0,
                metadata=error_metadata,
                is_active=False
            )
            
            self.db.add(failed_process)
            data_source.is_connected = False
            self.db.commit()
            
            raise e

    async def _calculate_size_info(self, data_source: DataSource, documents: list) -> Dict[str, Any]:
        """Calculate size information for the data source and its documents"""
        size_info = {
            'source_size': 0,
            'total_tokens': 0,
            'total_size': 0,
            'document_sizes': []
        }

        # Calculate source size for file uploads
        if data_source.source_type == "file_upload":
            file_path = data_source.connection_settings.get("file_path")
            if file_path and os.path.exists(file_path):
                size_info['source_size'] = os.path.getsize(file_path)

        # Initialize tokenizer
        tokenizer = tiktoken.get_encoding("cl100k_base")  # OpenAI's default tokenizer

        # Calculate size for each document
        for doc in documents:
            # Calculate tokens
            tokens = len(tokenizer.encode(doc.page_content))
            size_info['total_tokens'] += tokens

            # Calculate document size in bytes
            doc_size = len(doc.page_content.encode('utf-8'))
            size_info['document_sizes'].append(doc_size)
            size_info['total_size'] += doc_size

        # Add source size to total
        size_info['total_size'] += size_info['source_size']

        return size_info

    async def _calculate_vector_store_size(self, vector_store_path: str) -> int:
        """Calculate the size of the vector store directory"""
        vector_store_dir = f"db/vectorstore/{vector_store_path}"
        total_size = 0
        
        if os.path.exists(vector_store_dir):
            for dirpath, dirnames, filenames in os.walk(vector_store_dir):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(file_path)
        
        return total_size

    async def _calculate_processed_size(self, vector_store_path: str) -> int:
        """Calculate size of processed data (vector store)"""
        total_size = 0
        if os.path.exists(vector_store_path):
            for root, _, files in os.walk(vector_store_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
        return total_size 
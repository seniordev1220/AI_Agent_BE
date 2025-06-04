from ..utils.vector_db_manager import VectorDBManager
from ..utils.embedding_manager import EmbeddingManager
from ..utils.data_source_loader import DataSourceLoader
from ..models.vector_source import VectorSource
from ..models.api_key import APIKey
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class VectorService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.vector_db = VectorDBManager(user_id)
        
    async def get_user_sources(self, db: Session) -> List[VectorSource]:
        return db.query(VectorSource).filter(
            VectorSource.user_id == self.user_id
        ).all()

    async def get_source_by_id(self, source_id: int, db: Session) -> Optional[VectorSource]:
        return db.query(VectorSource).filter(
            VectorSource.id == source_id,
            VectorSource.user_id == self.user_id
        ).first()

    async def create_vector_source(
        self,
        name: str,
        source_type: str,
        connection_settings: Dict[str, Any],
        embedding_model: str,
        db: Session
    ) -> VectorSource:
        # Generate unique table name
        unique_id = str(uuid.uuid4())[:8]
        table_name = f"vector_{self.user_id}_{unique_id}_{name.lower().replace(' ', '_')}"
        
        vector_source = VectorSource(
            user_id=self.user_id,
            name=name,
            source_type=source_type,
            connection_settings=connection_settings,
            embedding_model=embedding_model,
            table_name=table_name
        )
        db.add(vector_source)
        db.commit()
        db.refresh(vector_source)

        try:
            # Process the data source
            await self.process_data_source(vector_source, db)
            # Update the timestamp after successful processing
            vector_source.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(vector_source)
        except Exception as e:
            print(f"Warning: Processing failed: {str(e)}")
            raise
            
        return vector_source

    async def process_data_source(self, vector_source: VectorSource, db: Session):
        try:
            # Synchronous operations
            self.vector_db.create_user_database()
            loader = DataSourceLoader(
                vector_source.source_type,
                vector_source.connection_settings
            )
            
            # Asynchronous operations
            documents = await loader.load_and_split()
            embedding_manager = EmbeddingManager(
                vector_source.embedding_model,
                self._get_api_key(vector_source.embedding_model, db)
            )
            
            vectors = []
            for doc in documents:
                embedding = await embedding_manager.get_embedding(doc["content"])
                vectors.append({
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "embedding": embedding
                })
            
            # Synchronous operation
            self.vector_db.create_source_table(
                vector_source.table_name,
                len(vectors[0]["embedding"])
            )
            
            # Asynchronous operation
            await self.vector_db.store_vectors(vector_source.table_name, vectors)
        except Exception as e:
            # Log the error or handle it appropriately
            print(f"Error processing data source: {str(e)}")
            raise

    def _get_api_key(self, model_name: str, db: Session) -> str:
        api_key = db.query(APIKey).filter(
            APIKey.user_id == self.user_id,
            APIKey.provider == self._get_provider(model_name),
            APIKey.is_valid == True
        ).first()
        if not api_key:
            raise ValueError(f"No valid API key found for model {model_name}")
        return api_key.api_key

    def _get_provider(self, model_name: str) -> str:
        if "openai" in model_name:
            return "openai"
        elif "gemini" in model_name:
            return "google"
        elif "claude" in model_name:
            return "anthropic"
        elif "deepseek" in model_name:
            return "deepseek"
        else:
            raise ValueError(f"Unknown provider for model {model_name}")

    async def search_similar(
        self,
        query: str,
        source_name: str,
        embedding_model: str,
        api_key: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        embedding_manager = EmbeddingManager(embedding_model, api_key)
        query_vector = await embedding_manager.get_embedding(query)
        results = await self.vector_db.search_vectors(
            source_name,
            query_vector,
            limit
        )
        return results

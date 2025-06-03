import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from typing import List, Dict, Any, Optional
import json

class VectorDBManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.db_name = f"vector_db_{user_id}"
        self.engine = None

    def _user_db_url(self) -> str:
        base = os.getenv("USER_DATABASE_URL_BASE")
        if not base:
            raise RuntimeError("USER_DATABASE_URL_BASE environment variable is not set!")
        return f"{base}{self.db_name}"
    
    def _admin_connection(self) -> psycopg2.extensions.connection:
        admin_url = os.getenv("ADMIN_DATABASE_URL")
        if not admin_url:
            raise RuntimeError("ADMIN_DATABASE_URL environment variable is not set!")
        conn = psycopg2.connect(admin_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn

    def create_user_database(self) -> None:
        """Create a new database for the user with vector extension enabled"""
        print(f"Creating database {self.db_name}")
        admin_conn = self._admin_connection()
        try:
            with admin_conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.db_name,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{self.db_name}"')
        finally:
            admin_conn.close()

        # Enable vector extension in the new database
        user_conn = psycopg2.connect(self._user_db_url())
        try:
            with user_conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            user_conn.commit()
        finally:
            user_conn.close()

        self.engine = create_engine(self._user_db_url())

    def ensure_engine(self) -> None:
        """Ensure database engine is initialized and vector extension exists"""
        if self.engine is None:
            self.engine = create_engine(self._user_db_url())
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    def create_source_table(self, source_name: str, dimension: int) -> None:
        """Create a table for storing vectors from a specific source"""
        self.ensure_engine()
        safe_table_name = source_name.replace('"', '""')
        
        query = text(f'''
        CREATE TABLE IF NOT EXISTS "{safe_table_name}" (
            id SERIAL PRIMARY KEY,
            content TEXT,
            metadata JSONB,
            embedding vector({dimension})
        )
        ''')
        
        with self.engine.connect() as conn:
            try:
                conn.execute(query)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to create table: {str(e)}")

    async def store_vectors(self, source_name: str, vectors: List[Dict[str, Any]]) -> None:
        """Store multiple vectors in the database"""
        self.ensure_engine()
        safe_table_name = source_name.replace('"', '""')
        
        query = text(f'''
        INSERT INTO "{safe_table_name}" (content, metadata, embedding)
        VALUES (:content, :metadata, :embedding)
        ''')
        
        with self.engine.begin() as conn:
            for vector in vectors:
                if isinstance(vector["metadata"], dict):
                    vector["metadata"] = json.dumps(vector["metadata"])
                conn.execute(query, vector)

    async def search_vectors(self, source_name: str, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar vectors in the database"""
        self.ensure_engine()
        safe_table_name = source_name.replace('"', '""')
        
        # Format the vector as a PostgreSQL array string
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        
        # Use CAST for proper type conversion
        query = text(f'''
        SELECT 
            content, 
            metadata, 
            1 - (embedding <=> CAST(:query_vector AS vector)) as similarity
        FROM "{safe_table_name}"
        ORDER BY similarity DESC
        LIMIT :limit
        ''')
        
        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {"query_vector": vector_str, "limit": limit}
            )
            rows = result.fetchall()
            formatted_results = []
            for row in rows:
                formatted_results.append({
                    "content": row[0],
                    "metadata": row[1],
                    "similarity": float(row[2])
                })
            return formatted_results

    def delete_source_table(self, table_name: str) -> None:
        """Delete a vector table"""
        self.ensure_engine()
        safe_table_name = table_name.replace('"', '""')
        query = text(f'DROP TABLE IF EXISTS "{safe_table_name}"')
        with self.engine.begin() as conn:
            conn.execute(query)

    def close(self) -> None:
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            self.engine = None

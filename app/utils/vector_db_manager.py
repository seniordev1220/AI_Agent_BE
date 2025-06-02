import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from typing import List, Dict, Any
import json

class VectorDBManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.db_name = f"vector_db_{user_id}"
        self.engine = None

    def _user_db_url(self):
        base = os.getenv("USER_DATABASE_URL_BASE")
        if not base:
            raise RuntimeError("USER_DATABASE_URL_BASE environment variable is not set!")
        return f"{base}{self.db_name}"
    
    def _admin_connection(self):
        admin_url = os.getenv("ADMIN_DATABASE_URL")
        if not admin_url:
            raise RuntimeError("ADMIN_DATABASE_URL environment variable is not set!")
        conn = psycopg2.connect(admin_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn

    def create_user_database(self):
        # Create database using admin connection
        print("Created Database")
        admin_conn = self._admin_connection()
        try:
            with admin_conn.cursor() as cur:
                # Check if database exists
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.db_name,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{self.db_name}"')
        finally:
            admin_conn.close()

        # Now connect to the new database to enable extension
        user_conn = psycopg2.connect(self._user_db_url())
        try:
            with user_conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            user_conn.commit()
        finally:
            user_conn.close()

        self.engine = create_engine(self._user_db_url())

    def ensure_engine(self):
        if self.engine is None:
            self.engine = create_engine(self._user_db_url())
            # Verify vector extension exists
            with self.engine.connect() as conn:
                try:
                    conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'vector'"))
                except:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    def create_source_table(self, source_name: str, dimension: int):
        self.ensure_engine()
        # Sanitize table name to prevent SQL injection
        safe_table_name = source_name.replace('"', '""')
        query = text(f'''
        CREATE TABLE IF NOT EXISTS "{safe_table_name}" (
            id SERIAL PRIMARY KEY,
            content TEXT,
            metadata JSONB,
            embedding vector(%s)
        )
        ''' % dimension)
        
        with self.engine.connect() as conn:
            try:
                conn.execute(query)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to create table: {str(e)}")

    async def store_vectors(self, source_name: str, vectors: List[Dict[str, Any]]):
        self.ensure_engine()
        safe_table_name = source_name.replace('"', '""')
        query = text(f'''
        INSERT INTO "{safe_table_name}" (content, metadata, embedding)
        VALUES (:content, :metadata, :embedding)
        ''')
        
        with self.engine.begin() as conn:  # auto-commit transaction
            for vector in vectors:
                if isinstance(vector["metadata"], dict):
                    vector["metadata"] = json.dumps(vector["metadata"])
                conn.execute(query, vector)

    def search_vectors(self, source_name: str, query_vector: List[float], limit: int = 5):
        self.ensure_engine()
        safe_table_name = source_name.replace('"', '""')
        query = text(f'''
        SELECT content, metadata, 1 - (embedding <=> :query_vector) as similarity
        FROM "{safe_table_name}"
        ORDER BY similarity DESC
        LIMIT :limit
        ''')
        
        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {"query_vector": query_vector, "limit": limit}
            )
            return result.fetchall()

    def delete_source_table(self, table_name: str):
        self.ensure_engine()
        safe_table_name = table_name.replace('"', '""')
        query = text(f'DROP TABLE IF EXISTS "{safe_table_name}"')
        with self.engine.begin() as conn:
            conn.execute(query)

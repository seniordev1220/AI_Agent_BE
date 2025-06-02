from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Boolean, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, index=True)
    source_type = Column(String)  # airtable, dropbox, gdrive, etc.
    connection_settings = Column(JSON)  # Store connection settings securely
    is_connected = Column(Boolean, default=False)
    raw_size_bytes = Column(BigInteger, default=0)  # Size of original data
    processed_size_bytes = Column(BigInteger, default=0)  # Size of processed data (vectors)
    total_tokens = Column(Integer, default=0)  # Number of tokens
    document_count = Column(Integer, default=0)  # Number of documents
    last_sync = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    user = relationship("User") 

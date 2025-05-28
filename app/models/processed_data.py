from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class ProcessedData(Base):
    __tablename__ = "processed_data"

    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"))
    vector_store_path = Column(String)  # Path to the Chroma DB
    document_count = Column(Integer)  # Number of documents processed
    data_metadata = Column(JSON, name="metadata")
    is_active = Column(Boolean, default=True)
    last_processed = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    total_tokens = Column(Integer, nullable=True)
    processed_size_bytes = Column(Integer)
    total_size_bytes = Column(Integer, nullable=True)
    chunk_count = Column(Integer)

    # Relationship
    data_source = relationship("DataSource", backref="processed_data") 
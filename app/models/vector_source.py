from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, func, Boolean
from sqlalchemy.orm import relationship
from ..database import Base

class VectorSource(Base):
    __tablename__ = "vector_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # csv, pdf, etc.
    connection_settings = Column(JSON)
    embedding_model = Column(String, nullable=False)
    table_name = Column(String, nullable=False, unique=True)
    is_converted = Column(Boolean, default=False)  # Flag to track vector conversion status
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="vector_sources")

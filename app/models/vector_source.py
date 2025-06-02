from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime, func
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="vector_sources")
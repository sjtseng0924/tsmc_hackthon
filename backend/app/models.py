from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    source_filename = Column(String, index=True)
    chunk_index = Column(Integer)
    content = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

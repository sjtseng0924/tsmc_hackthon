from sqlalchemy import Column, Integer, String, Text, DateTime, func, JSON, ForeignKey
from app.database import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship

# Knowledge Chunk Model
class Knowledge(Base):
    __tablename__ = "knowledge"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True) # filename
    content = Column(Text)
    vector = Column(Vector(768))
    case_id = Column(String, index=True)
    title = Column(String)
    category = Column(String)
    severity = Column(String)
    summary = Column(Text)
    root_cause = Column(Text)
    timeline = Column(JSON)
    immediate_fix = Column(Text)
    long_term_fix = Column(Text)
    tags = Column(JSON)
    references = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

    # 一個 knowledge 對應多則訊息討論
    messages = relationship("Message", back_populates="knowledge", cascade="all, delete-orphan")

# Log File Model
class LogFile(Base):
    __tablename__ = "log_files"
    id = Column(Integer, primary_key=True, index=True)
    scenario = Column(Integer, index=True)
    filename = Column(String, index=True)
    entries = relationship("LogEntry", back_populates="file", cascade="all, delete-orphan")

class LogEntry(Base):
    __tablename__ = "log_entries"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey('log_files.id'), nullable=False)
    file = relationship("LogFile", back_populates="entries")
    line_number = Column(Integer, nullable=False)
    timestep = Column(DateTime, nullable=True)
    raw_content = Column(Text, nullable=False)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    # foreign key to knowledge table
    knowledge_id = Column(Integer, ForeignKey('knowledge.id'), nullable=True, index=True)
    knowledge = relationship("Knowledge", back_populates="messages")
    
    external_id = Column(String, unique=True, index=True)  # e.g., Discord message.id
    timestamp = Column(DateTime, nullable=True)
    user = Column(String, nullable=True)
    role = Column(String, nullable=True)
    scenario = Column(Integer, index=True)
    content = Column(Text, nullable=False)

# Code Model
class Code(Base):
    __tablename__ = "codes"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True)
    content = Column(Text)  # code content
    vector = Column(Vector(768))

# Contact Model - Maps names to email addresses and Discord IDs
class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)  # Display name (case-insensitive index)
    email = Column(String, nullable=False, unique=True, index=True)  # Gmail address
    discord_id = Column(String, nullable=True, unique=True, index=True)  # Discord user ID
    department = Column(String, nullable=True)  # Optional: department/team
    is_active = Column(Integer, default=1)  # 1=active, 0=inactive
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

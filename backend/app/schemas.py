from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 基礎欄位 (Shared properties)
class KnowledgeChunkBase(BaseModel):
    source_filename: str
    chunk_index: int
    content: str

# 建立時需要的欄位 (Creation)
class KnowledgeChunkCreate(KnowledgeChunkBase):
    pass

# 從資料庫讀取出來的完整欄位 (Reading / Return to frontend)
class KnowledgeChunk(KnowledgeChunkBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
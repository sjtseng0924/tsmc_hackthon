from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

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


class CaseReference(BaseModel):
    label: str
    url: str


class CaseItem(BaseModel):
    id: str
    title: str
    category: str
    severity: str
    rootCause: str
    tags: List[str]
    summary: str
    timeline: List[str]
    immediateFix: str
    longTermFix: str
    references: List[CaseReference]


class CaseListResponse(BaseModel):
    total: int
    items: List[CaseItem]


class TaxonomyResponse(BaseModel):
    categories: List[str]
    severities: List[str]
    tags: List[str]


# Messages linked to knowledge
class MessageBase(BaseModel):
    knowledge_id: Optional[int] = None
    timestamp: datetime  # 訊息時間（同 created_at 概念）
    user: Optional[str] = None
    role: Optional[str] = None
    content: str


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: int

    class Config:
        from_attributes = True

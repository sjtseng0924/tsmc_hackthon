from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any

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


class PreventionMeasure(BaseModel):
    title: str
    content: str
    owner: str
    link: Optional[str] = None


class CaseItem(BaseModel):
    filename: str  # Was id
    title: str
    severity: str
    
    # New structured fields
    reportDate: Optional[str] = None
    occurredAt: Optional[str] = None
    resolvedAt: Optional[str] = None
    
    reportProblem: Optional[str] = None
    impactService: Optional[str] = None
    impactUser: Optional[str] = None
    impactData: Optional[str] = None
    
    rootCause: str
    eventDetails: Optional[str] = None
    timeline: List[str]
    inferenceProcess: Optional[str] = None
    
    solution: Optional[str] = None
    preventiveMeasures: List[PreventionMeasure] = [] 
    hiddenRisks: Optional[Any] = None # JSON structure

    summary: Optional[str] = None # For backward compatibility in frontend display


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
    external_id: str
    timestamp: datetime
    user: Optional[str] = None
    role: Optional[str] = None
    content: str


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: int

    class Config:
        from_attributes = True

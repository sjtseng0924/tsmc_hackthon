import os
import vertexai
from vertexai.language_models import TextEmbeddingModel
from app.config import settings
from app.database import SessionLocal
from app.models import Knowledge, Code

def get_embedding(text: str):
    """將文字轉成向量 (768維)"""
    vertexai.init(
        project=settings.VERTEX_PROJECT,
        location=settings.VERTEX_EMBEDDING_LOCATION
    )
    
    model = TextEmbeddingModel.from_pretrained(settings.EMBEDDING_MODEL)
    # Force embedding size to match the pgvector column (vector(768))
    embeddings = model.get_embeddings([text], output_dimensionality=768)
    return embeddings[0].values

def retrieve_knowledge(query: str, limit: int = 3) -> str:
    """
    [RAG Tool] 知識庫搜尋工具
    
    Args:
        query: 使用者的搜尋問題 (e.g., "權限不足怎麼辦")
        limit: 回傳幾筆資料 (預設 3)
    """
    try:
        # 1. 把問題轉成向量
        query_vector = get_embedding(query)
        
        db = SessionLocal()
        try:
            # 2. 用向量算距離 (L2 Distance)，找最近的鄰居
            results = db.query(Knowledge)\
                .order_by(Knowledge.vector.l2_distance(query_vector))\
                .limit(limit)\
                .all()

            if not results:
                return "知識庫中找不到相關資料。"

            # 3. 組合回傳結果
            context_parts = []
            for doc in results:
                # 簡單過濾分數太低的結果 (非必須，視需求而定)
                context_parts.append(f"【文件: {doc.filename}】\n{doc.content}")
            
            return "\n\n".join(context_parts)
            
        finally:
            db.close()
    except Exception as e:
        return f"搜尋發生錯誤: {str(e)}"

def list_knowledge_files(limit: int = 20) -> str:
    """
    List available files in the knowledge base/history.
    Use this tool when the user asks specifically to "list history", "show available documents", or "what do you know in history?".
    returns: A list of unique filenames found in the knowledge base.
    """
    db = SessionLocal()
    try:
        files = db.query(Knowledge.filename).distinct().limit(limit).all()
        if not files:
            return "Knowledge base is empty."
        
        file_list = [f[0] for f in files]
        return "Available Knowledge Files:\n" + "\n".join(f"- {name}" for name in file_list)
    except Exception as e:
        return f"Error listing knowledge files: {str(e)}"
    finally:
        db.close()
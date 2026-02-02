# gemini.py
import os
import json
import vertexai
from vertexai import agent_engines
from app.config import settings
from app.services.rag import list_knowledge_files, retrieve_knowledge
from app.tools.calendar import list_events, create_event, check_availability


_agent = None


def init_models():
    global _agent
    if _agent is None:
        # 設置認證
        creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        if creds_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        
        vertexai.init(
            project=settings.VERTEX_PROJECT,
            location=settings.VERTEX_AGENT_LOCATION,
        )
        _agent = agent_engines.LanggraphAgent(
            model=settings.AGENT_MODEL,
            tools=[
                list_knowledge_files, 
                retrieve_knowledge,
                list_events,
                create_event,
                check_availability
            ],
            model_kwargs={
                "temperature": 0.2,
                "max_output_tokens": 800,
                "top_p": 0.95,
            },
        )


def run_agent(
    user_message: str,
    rag_context: str = "",
) -> dict:
    init_models()

    prompt = f"""
你是一個 IT 事故處理助手 (IT Incident Assistant)。
你的任務是協助團隊解決系統故障，協調人員，並記錄事故。
你可以查看知識庫、查詢日曆、確認人員是否有空（例如 Ivan），並發起會議邀請。
目前的場景通常涉及緊急事故，例如資料遺失或服務中斷。請展現專業、冷靜且主動的態度。

使用者輸入：{user_message}
歷史參考：
{rag_context}
"""

    response = _agent.query(input={"messages": [("user", prompt)]})

    if isinstance(response, str):
        try:
            return json.loads(response)
        except Exception:
            return {"message": response, "confidence": 0.0}

    if isinstance(response, dict) and "messages" in response:
        for msg in reversed(response["messages"]):
            msg_type = msg.get("kwargs", {}).get("type")
            if msg_type == "ai":
                content = msg.get("kwargs", {}).get("content", "")
                return {"message": content, "raw": response}

    return {"message": str(response), "raw": response}

# gemini.py
import os
import json
import vertexai
from vertexai import agent_engines
from app.config import settings


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
            location=settings.VERTEX_LOCATION,
        )
        _agent = agent_engines.LanggraphAgent(
            model="gemini-3-pro-preview",
            tools=[],
            model_kwargs={
                "temperature": 0.2,
                "max_output_tokens": 800,
                "top_p": 0.95,
            },
        )


def run_agent(
    user_message: str,
    rag_context: str,
) -> dict:
    init_models()

    prompt = f"""
你是一個手機 App 使用助手。
使用者輸入：{user_message}
歷史參考：
{rag_context}

請只輸出 JSON。
"""

    response = _agent.query(input={"messages": [("user", prompt)]})

    if isinstance(response, str):
        try:
            return json.loads(response)
        except Exception:
            return {"message": response, "confidence": 0.0}

    return response

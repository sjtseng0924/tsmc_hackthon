# gemini.py
import os
import json
import vertexai
from vertexai.generative_models import GenerativeModel

_model = None


def init_models():
    global _model
    if _model is None:
        # 設置認證
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        
        vertexai.init(
            project=os.environ.get("VERTEX_PROJECT", "your-gcp-project-id"),
            location=os.environ.get("VERTEX_LOCATION", "us-central1"),
        )
        _model = GenerativeModel("gemini-2.5-flash")


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

    response = _model.generate_content(prompt)
    try:
        return json.loads(response.text)
    except Exception:
        return {
            "message": response.text,
            "confidence": 0.0,
        }

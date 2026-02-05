# gemini.py
import os
import json
from typing import Optional

import vertexai
from vertexai import agent_engines

from app.config import settings
from app.services.assistant_tools import (
    get_case_report,
    get_code_file,
    list_case_reports,
    list_code_files,
    list_log_files,
    list_recent_discord_messages,
    search_code_snippets,
    search_discord_messages,
    search_log_entries,
)
from app.services.rag import retrieve_knowledge
from app.tools.calendar import list_events, create_event, check_availability


_summary_agent = None
_summary_all_agent = None
_solution_agent = None
_calendar_agent = None
_vertex_initialized = False


def _init_vertex():
    global _vertex_initialized
    if _vertex_initialized:
        return
    creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if creds_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

    vertexai.init(
        project=settings.VERTEX_PROJECT,
        location=settings.VERTEX_AGENT_LOCATION,
    )
    _vertex_initialized = True


def _build_agent(tools: list) -> agent_engines.LanggraphAgent:
    return agent_engines.LanggraphAgent(
        model=settings.AGENT_MODEL,
        tools=tools,
        model_kwargs={
            "temperature": 0.2,
            "max_output_tokens": 2000,
            "top_p": 0.95,
        },
    )


def init_models():
    global _summary_agent, _summary_all_agent, _solution_agent, _calendar_agent
    if (
        _summary_agent is not None
        and _summary_all_agent is not None
        and _solution_agent is not None
        and _calendar_agent is not None
    ):
        return

    _init_vertex()

    summary_tools = []
    summary_all_tools = []

    calendar_tools = [
        list_events,
        create_event,
        check_availability,
    ]

    solution_tools = [
        list_recent_discord_messages,
        search_discord_messages,
        list_log_files,
        search_log_entries,
        list_code_files,
        search_code_snippets,
        get_code_file,
        list_case_reports,
        get_case_report,
        retrieve_knowledge,
    ]

    _summary_agent = _build_agent(summary_tools)
    _summary_all_agent = _build_agent(summary_all_tools)
    _solution_agent = _build_agent(solution_tools)
    _calendar_agent = _build_agent(calendar_tools)


def _detect_intent(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(keyword in text for keyword in ["結案報告", "事故結案", "post-mortem", "post mortem", "結案"]):
        return "summary_all"
    if any(keyword in text for keyword in ["行程", "日曆", "行事曆", "會議", "邀請", "空檔", "有空", "可用時間"]):
        return "calendar"
    if any(keyword in text for keyword in ["報案問題", "影響範圍"]):
        return "summary_problem"
    if any(keyword in text for keyword in ["怎麼解決", "如何解決", "解決", "修復", "排除", "處理"]):
        return "solution"
    return "solution"


def _history_to_text(history: Optional[list[dict]]) -> str:
    if not history:
        return ""
    lines = []
    for item in history[-12:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_prompt(user_message: str, mode: str, history: str, rag_context: str) -> str:
    if mode == "summary_all":
        return _build_summary_all_prompt(user_message, history, rag_context)
    if mode == "summary_problem":
        return _build_summary_prompt(user_message, history, rag_context)
    if mode == "calendar":
        return _build_calendar_prompt(user_message, history, rag_context)
    return _build_solution_prompt(user_message, history, rag_context)


def _build_summary_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：summary_problem（統整報案問題與影響範圍，只能使用對話紀錄內容）。\n"
        "請用純文字回覆並包含以下區段：\n"
        "報案問題\n"
        "(兩到三句話統整使用者描述的問題)\n\n"
        "影響範圍\n"
        "服務影響: ...\n"
        "使用者影響: ...\n"
        "資料影響: ...\n"
        "注意：只能輸出以上兩個區段，不要加其他文字。\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_summary_all_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：summary_all（產出完整結案報告）。\n"
        "請嚴格依照下列格式輸出，不要加多餘文字：\n\n"
        "tNote 系統事故結案報告 (Post-Mortem Report)\n\n"
        "文件編號: (若對話或資料有編號就使用，沒有請填未知)\n"
        "報告日期: (若對話或資料有日期就使用，沒有請填未知)\n"
        "事件標題: (若對話或資料有標題就使用，沒有請填未知)\n\n"
        "1. 基本資訊\n\n"
        "Issue 發生時間: (若對話或資料有時間就使用，沒有請填未知)\n\n"
        "Issue 解決時間: (若對話或資料有時間就使用，沒有請填未知)\n\n"
        "事件等級: (若對話或資料有等級就使用，沒有請填未知)\n\n"
        "2. 報案問題\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "3. 影響範圍\n\n"
        "服務影響:\n\n"
        "使用者影響:\n\n"
        "資料影響:\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "4. Issue 發生細節描述\n\n"
        "根本原因 (Root Cause):\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "事件細節:\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "事件時間軸:\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "5. 解決方案 (Immediate Fix)\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "6. 之後如何避免 (Prevention Measures)\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "注意：優先使用對話紀錄中的既有內容；只有缺少時才補寫。\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_calendar_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：calendar（查詢/安排日曆，只能使用日曆相關工具）。\n"
        "請用簡短條列回覆，格式如下：\n"
        "- 需求: (使用者要做的日曆需求)\n"
        "- 行動: (你要查詢/建立/檢查的項目)\n"
        "- 結果: (查詢到的結果或建立成功的摘要)\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_solution_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：solution（協助解決問題，可使用對話紀錄、log、code、結案報告工具）。\n"
        "請一次完成並輸出最終結果，只輸出兩段(回復不能為空非常重要)，不要輸出底下在括號內的字，格式請用\n"
        "   Issue 發生細節描述:\n 根本原因(用一兩句話總結整個問題)\n事件時間軸(詳細寫出在每個開過的檔案中的推理，逐條列出什麼時間點發生甚麼)\n"
        "   解決方案: (列出每個面向的問題以及解決方法)\n"
        "   並在每段中標示參考檔案名稱（例如：tNote_app_server_v1.log, INC-20230815-04）。\n"
        "避免重複查看相同來源；資料足夠就直接總結。\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def run_agent(
    user_message: str,
    rag_context: str = "",
    conversation_history: Optional[list[dict]] = None,
    mode: Optional[str] = None,
) -> dict:
    init_models()

    resolved_mode = mode or _detect_intent(user_message)
    history_text = _history_to_text(conversation_history)
    summary_context = ""
    if resolved_mode == "summary_problem":
        summary_context = _build_summary_context(user_message)
    if resolved_mode == "summary_all":
        summary_context = _build_summary_all_context(user_message)
    prompt = _build_prompt(
        user_message,
        resolved_mode,
        history_text,
        rag_context or summary_context,
    )

    if resolved_mode == "summary_problem":
        agent = _summary_agent
    elif resolved_mode == "summary_all":
        agent = _summary_all_agent
    elif resolved_mode == "calendar":
        agent = _calendar_agent
    else:
        agent = _solution_agent
    response = agent.query(input={"messages": [("user", prompt)]})

    if isinstance(response, str):
        try:
            return json.loads(response)
        except Exception:
            return {
                "message": response,
                "structured": _parse_structured_response(response, resolved_mode),
                "mode": resolved_mode,
                "confidence": 0.0,
            }

    if isinstance(response, dict) and "messages" in response:
        for msg in reversed(response["messages"]):
            msg_type = msg.get("kwargs", {}).get("type")
            if msg_type == "ai":
                content = msg.get("kwargs", {}).get("content", "")
                if not content:
                    content = _fallback_message(resolved_mode)
                return {
                    "message": content,
                    "structured": _parse_structured_response(content, resolved_mode),
                    "mode": resolved_mode,
                    "raw": response,
                }

    if not response:
        return {
            "message": _fallback_message(resolved_mode),
            "structured": None,
            "mode": resolved_mode,
            "raw": response,
        }
    return {
        "message": str(response),
        "structured": _parse_structured_response(str(response), resolved_mode),
        "mode": resolved_mode,
        "raw": response,
    }


def _parse_structured_response(content: str, mode: str) -> Optional[dict]:
    if mode != "solution":
        return None
    if not content:
        return None
    try:
        data = json.loads(content)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if "status" not in data or "reply" not in data:
        return None
    return data


def _build_summary_context(user_message: str) -> str:
    parts = [list_recent_discord_messages(limit=20)]
    if user_message and len(user_message.strip()) >= 2:
        parts.append(search_discord_messages(user_message, limit=20))
    return "\n\n".join(p for p in parts if p)


def _build_summary_all_context(user_message: str) -> str:
    parts = [list_recent_discord_messages(limit=40)]
    if user_message and len(user_message.strip()) >= 2:
        parts.append(search_discord_messages(user_message, limit=40))
    return "\n\n".join(p for p in parts if p)


def _fallback_message(mode: str) -> str:
    if mode == "summary_all":
        return (
            "目前沒有足夠的對話紀錄可以產出結案報告。\n"
            "請提供更多討論內容或貼上關鍵段落。"
        )
    if mode == "summary_problem":
        return (
            "目前沒有足夠的對話紀錄可以統整。\n"
            "請提供更多描述，或先貼上相關討論內容。"
        )
    if mode == "calendar":
        return "目前無法取得日曆資訊，請再描述具體需求。"
    return "目前無法取得回覆內容，請再試一次。"

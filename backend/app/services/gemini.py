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
            "max_output_tokens": 900,
            "top_p": 0.95,
        },
    )


def init_models():
    global _summary_agent, _solution_agent, _calendar_agent
    if (
        _summary_agent is not None
        and _solution_agent is not None
        and _calendar_agent is not None
    ):
        return

    _init_vertex()

    summary_tools = [
        list_recent_discord_messages,
        search_discord_messages,
    ]

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
    _solution_agent = _build_agent(solution_tools)
    _calendar_agent = _build_agent(calendar_tools)


def _detect_intent(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(keyword in text for keyword in ["行程", "日曆", "行事曆", "會議", "邀請", "空檔", "有空", "可用時間"]):
        return "calendar"
    if any(keyword in text for keyword in ["影響範圍", "影響", "統整", "彙整", "摘要", "總結"]):
        return "summary"
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
    mode_rules = (
        "模式一：使用者要統整問題與影響範圍，只能使用 Discord 對話紀錄工具。\n"
        "模式二：使用者詢問如何解決，允許使用 Discord 對話紀錄、log、code、結案報告工具。\n"
        "模式三：使用者要查詢/安排日曆或時間，只能使用日曆相關工具。\n"
    )
    solution_output = (
        "若本次模式為 solution，請用 JSON 格式回覆："
        "{\"status\": \"continue\"|\"final\", \"progress\": ["
        "\"目前在看: <來源或檔名>\"], \"reply\": \"給使用者的內容\"}。\n"
        "當還需要繼續查找或呼叫更多工具時，status=continue；已完成結論時，status=final。\n"
    )
    progress_rule = (
        "當你要查看某個資料來源或檔案時，請在回覆中加入一行："
        "『目前在看: <來源或檔名>』，讓使用者知道你正在看的內容。\n"
    )
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        f"{mode_rules}"
        f"本次模式: {mode}\n"
        f"{progress_rule}"
        f"{solution_output}"
        "若需要工具就呼叫對應的 function。\n"
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
    prompt = _build_prompt(user_message, resolved_mode, history_text, rag_context)

    if resolved_mode == "summary":
        agent = _summary_agent
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
                return {
                    "message": content,
                    "structured": _parse_structured_response(content, resolved_mode),
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

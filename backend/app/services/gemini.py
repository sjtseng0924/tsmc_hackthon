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

    summary_tools = []

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
    if any(keyword in text for keyword in ["報案問題", "影響範圍", "影響", "統整", "彙整", "摘要", "總結"]):
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
    progress_rule = (
        "當你要查看某個資料來源或檔案時，請回覆兩行："
        "『目前在看: <來源或檔名>』，讓使用者知道你正在看的內容。\n"
        "『原因: <為什麼要看這個來源>』，讓使用者知道為什麼看(因為使用者的甚麼敘述, 因為上一個檔案的什麼內容等)。\n"
    )
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：solution（協助解決問題，可使用對話紀錄、log、code、結案報告工具）。\n"
        f"{progress_rule}"
        "請用純文字回覆並包含以下區段：\n"
        "- 目前在看: <來源或檔名>\n"
        "- 原因: 為什麼要看這個來源\n"
        "- 狀態: 給使用者看的描述（例如：我會再繼續查看其他檔案）\n"
        "- 總結: 最終結論（只有在完成時輸出）\n"
        "若尚未完成，請不要輸出總結。\n"
        "當你還需要繼續時，請在回覆最後加上內部標記 [[CONTINUE]]；完成時不要加。\n"
        "更新內容會立即發送到 Discord，請用完整句子說明你正在看什麼與原因。\n"
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
    prompt = _build_prompt(
        user_message,
        resolved_mode,
        history_text,
        rag_context or summary_context,
    )

    if resolved_mode == "summary_problem":
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


def _fallback_message(mode: str) -> str:
    if mode == "summary_problem":
        return (
            "目前沒有足夠的對話紀錄可以統整。\n"
            "請提供更多描述，或先貼上相關討論內容。"
        )
    if mode == "calendar":
        return "目前無法取得日曆資訊，請再描述具體需求。"
    return "目前無法取得回覆內容，請再試一次。"

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
    search_industry_standards,
)
from app.services.rag import retrieve_knowledge
from app.tools.calendar import list_events, create_event, check_availability, find_available_slots


_summary_agent = None
_summary_all_agent = None
_solution_agent = None
_future_agent = None
_calendar_agent = None
_vertex_initialized = False


def _init_vertex():
    global _vertex_initialized
    if _vertex_initialized:
        return

    # 設置認證
    creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if creds_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    
    vertexai.init(
        project=settings.VERTEX_PROJECT,
        location=settings.VERTEX_AGENT_LOCATION,
    )
    _vertex_initialized = True


def _build_agent(tools):
    return agent_engines.LanggraphAgent(
        model=settings.AGENT_MODEL,
        tools=tools,
        model_kwargs={
            "temperature": 0.2,
            "max_output_tokens": 20000,
            "top_p": 0.95,
        },
    )


def init_models():
    global _summary_agent, _summary_all_agent, _solution_agent, _future_agent, _calendar_agent
    
    # Check if already initialized
    if (
        _summary_agent is not None
        and _summary_all_agent is not None
        and _solution_agent is not None
        and _future_agent is not None
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
        find_available_slots,
    ]

    future_tools = [
        search_industry_standards,
        list_log_files,
        search_log_entries,
        list_code_files,
        search_code_snippets,
        get_code_file,
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
    _future_agent = _build_agent(future_tools)


def _detect_intent(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(keyword in text for keyword in ["結案報告", "事故結案", "post-mortem", "post mortem", "結案"]):
        return "summary_all"
    if any(keyword in text for keyword in ["行程", "日曆", "行事曆", "會議", "邀請", "空檔", "有空", "可用時間"]):
        return "calendar"
    if any(keyword in text for keyword in ["報案問題", "影響範圍"]):
        return "summary_problem"
    if any(keyword in text for keyword in ["如何改進", "未來改進", "改善", "提升", "預防", "防範", "改進"]):
        return "future_improve"
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
    if mode == "future_improve":
        return _build_future_prompt(user_message, history, rag_context)
    return _build_solution_prompt(user_message, history, rag_context)


def _build_future_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "模式：未來改進（針對這次的問題提出對於程式碼的改進建議）\n"
        "建議先使用 Log/Code 工具查看系統內部的錯誤特徵或實作模式（搜尋 logs 或搜尋 code 找不當或可優化的寫法）\n"
        "再用 Google Search 工具查詢該問題的業界標準/改進方案 (improvements)，若在項目中有提及，可選擇在格式中多一項 參考連結：[外部網址]\n"
        "最後結合內部現狀與外部標準。\n"
        "請嚴格依照以下純文字的形式輸出，並且不要有格式限制以外的文字輸出\n\n"
        "## 之後如何避免\n"
        "- 未來預防措施\n"
        "格式範例：\n"
        "預防措施 1: (標題，是針對這次發生的問題具體可以預防的建議)\n\n"
        "內容: (清楚的提出完整的實施方法)\n"
        "負責人: (建議負責團隊，如 Infra Team, SRE Team, DevOps Team, Security Team, DBA Team)\n"
        "參考連結: (請一定要附上找到的參考連結)\n\n"
        "(請依序產出多個預防措施)\n\n"
        "- 其他隱藏的危險及優化方法\n"
        "請具體提出是因為哪個 Log 或 Code 有效率低下的寫法或錯誤用法，提出具體的潛在風險預警或優化建議\n"
        "並在下一行一定要附上找到的參考連結\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_summary_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：summary_problem（統整報案問題與影響範圍，只能使用對話紀錄內容）。\n"
        "請用純文字回覆並包含以下區段：\n"
        "## 報案問題\n"
        "(兩到三句話統整使用者描述的問題)\n\n"
        "## 影響範圍\n"
        "- 服務影響: ...\n"
        "- 使用者影響: ...\n"
        "- 資料影響: ...\n"
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
        "請嚴格依照下列格式輸出，不要加多餘文字，從對話紀錄找到相關內容務並內容都整理輸出，除了數字以外的分點都用點來表示，縮排務必整齊\n\n"
        "tNote 系統事故結案報告 (Post-Mortem Report)\n\n"
        "文件編號: (請依使用者@bot請求結案報告的日期與時間命名為 INC-YYYYMMDD-HHMM)\n"
        "報告日期: (若對話或資料有日期就使用，沒有請填未知)\n"
        "事件標題: (若對話或資料有標題就使用，沒有請填未知)\n\n"
        "1. 基本資訊\n\n"
        "Issue 發生時間: (若對話或資料有時間就使用，沒有請填未知)\n\n"
        "Issue 解決時間: (請使用使用者@bot提出結案報告需求的時間)\n\n"
        "事件等級: (若對話或資料有等級就使用，沒有請依下列標準判斷)\n"
        "(以下是參考的分級標準不印出)"
        "P0: 全站/核心服務不可用或大規模資料風險\n"
        "P1: 主要功能不可用或大量使用者受影響\n"
        "P2: 部分功能異常或有限使用者受影響\n"
        "P3: 輕微問題或體驗/效能影響\n\n"
        "(以上是參考的分級標準不印出)"
        "2. 報案問題\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "3. 影響範圍\n\n"
        "- 服務影響\n\n"
        "- 使用者影響\n\n"
        "- 資料影響\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "4. Issue 發生細節描述\n\n"
        "- 根本原因\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "- 事件細節\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "- 事件時間軸\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "- 檔案閱讀推理過程\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "5. 解決方案\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "6. 之後如何避免\n\n"
        "- 未來預防措施\n\n"
        "預防措施 X: (標題，是針對這次發生的問題具體可以預防的建議)\n\n"
        "內容: (清楚的提出完整的實施方法)\n"
        "負責人: (建議負責團隊，如 Infra Team, SRE Team, DevOps Team, Security Team, DBA Team)\n"
        "參考連結: (請一定要附上找到的參考連結)\n\n"
        "(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\n\n"
        "- 其他隱藏的危險及優化方法\n\n"
        "請具體提出是因為哪個 Log 或 Code 有效率低下的寫法或錯誤用法，提出具體的潛在風險預警或優化建議\n"
        "並在下一行一定要附上找到的參考連結\n"
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
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    return (
        "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
        "請使用繁體中文，保持專業、冷靜與條理。\n"
        "模式：calendar（查詢/安排日曆）。\n"
        "所在時區：Asia/Taipei (GMT+8)\n"
        f"現在時間是：{now_str} (請以此時間為基準推斷「現在」、「這週」等相對日期)\n"
        "注意：如果外部工具回傳 UTC 時間 (例如結尾為 Z 的時間)，請務必將其轉換為 GMT+8 後再回答使用者。\n\n"
        "**日曆助手進階策略：**\n\n"
        "**重要：可用性查詢行為**\n"
        "- `check_availability` 和 `find_available_slots` 現在功能完全相同\n"
        "- 它們會同時回傳：\n"
        "  1. 當前時段是否有空（available: true/false）\n"
        "  2. 接下來 2 天內最快的空檔（next_free_slot）\n"
        "- 使用任一工具都可以，它們回傳的資料格式一樣\n\n"
        "1. **緊急找人 (Mobilize)**：\n"
        "   - 當使用者問「Ivan 在嗎？」、「Ivan 有空嗎？」或「拉 Ivan 進來」，**預設時間為 現在 (Now)** 至 30 分鐘後。\n"
        "   - 使用 `check_availability` 工具。若不知道 Email，直接使用人名 (如 'Ivan')，系統會自動嘗試查詢。\n"
        "   - 回答範例：「Ivan 目前是忙碌狀態（會議中）。不過接下來的空檔是今天下午 2:30 - 3:30。」\n\n"
        "2. **建立 War Room (Emergency Sync)**：\n"
        "   - 當聽到「緊急會議」、「War Room」或「線上同步」：\n"
        "     - **summary**: 必須加上 `[Emergency]` 前綴 (例如: `[Emergency] tNote DB Outage War Room`)。\n"
        "     - **description**: 請將目前的對話摘要放入描述中，讓與會者知道發生什麼事。\n"
        "     - **is_allday**: False。\n"
        "     - **attendees**: 自動加入對話中提到的所有相關人員。\n\n"
        "3. **事後檢討 (Post-Mortem)**：\n"
        "   - 當使用者要求「約檢討會」或「Post-Mortem」：\n"
        "     - 先呼叫 `check_availability` 或 `find_available_slots` 查詢關鍵人員。\n"
        "     - 使用回傳的 `next_free_slot`，**主動推薦**一個大家都有空的時間 (例如「明天下午 14:00 - 15:00 大家都有空」)。\n"
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
        "模式：solution（協助解決問題，務必交叉查閱對log、code、結案報告，在每一次的查閱中找到下一次要看的檔案並使用函式，務必這四種每一種調閱都要試過）\n"
        "請一次完成並輸出最終結果，只輸出兩段(回復不能為空非常重要)，不要輸出底下括號內的文字，務必不要查看重複的檔案超過兩次\n"
        "## Issue 發生細節描述\n"
        "- 根本原因(用一兩句話總結整個問題)\n"
        "- 事件時間軸(詳細寫出在每個開過的檔案中的推理，逐條列出什麼時間點發生甚麼)\n"
        "- 檔案閱讀推理過程(詳細寫說是在code, log中看到什麼才決定打開什麼檔案並在其中搜尋甚麼發現甚麼)\n"
        "## 解決方案(列出每個面向的問題以及解決方法)\n"
        "並在每段中標示參考檔案名稱（例如：tNote_app_server_v1.log, INC-20230815-04）。\n"
        "避免重複查看相同來源，資料足夠就直接總結。\n"
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

    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    elif resolved_mode == "future_improve":
        agent = _future_agent
    else:
        agent = _solution_agent
    response = agent.query(
        input={"messages": [("user", prompt)]},
        config={"recursion_limit": 60},
    )

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
            
            # Log usage of tools if any
            if "tool_calls" in msg.get("kwargs", {}):
                print(f"DEBUG: Tool Calls detected: {msg.get('kwargs', {})['tool_calls']}")

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
    if mode == "future_improve":
        return "目前無法產生改進建議，請提供更多情境或既有問題描述。"
    return "目前無法取得回覆內容，請再試一次。"

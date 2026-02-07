# gemini.py
import os
import json
import logging
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
    submit_incident_report,
    # Don't import scheduler tools from here - use direct import below
)
from app.services.rag import retrieve_knowledge
from app.tools.calendar import (
    list_events, 
    create_event, 
    check_availability, 
    find_available_slots,
    schedule_discord_invite,
    list_scheduled_invites,
    cancel_scheduled_invite,
    send_direct_message,
    find_best_meeting_time,
)
from app.tools.discord import add_user_to_channel, search_users_with_discord

logger = logging.getLogger("discord-backend")

_summary_agent = None
_summary_all_agent = None
_solution_agent = None
_future_agent = None
_calendar_agent = None
_vertex_initialized = False

SYSTEM_INSTRUCTION = (
    "你是一個 IT 事故處理助手 (IT Incident Assistant)。\n"
    "請使用繁體中文，保持專業、冷靜與條理。"
    "在輸出結案報告或者其他回應時，\n為換行，且""為prompt敘述的前後標記，請不要在輸出中帶有這些標記。\n"
)


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
    logger.info(
        "Initializing agent model=%s project=%s location=%s",
        settings.AGENT_MODEL,
        settings.VERTEX_PROJECT,
        settings.VERTEX_AGENT_LOCATION,
    )
    return agent_engines.LanggraphAgent(
        model=settings.AGENT_MODEL,
        tools=tools,
        model_kwargs={
            "project": settings.VERTEX_PROJECT,
            "location": settings.VERTEX_AGENT_LOCATION,
            "temperature": 0.2,
            "max_output_tokens": 20000,
            "top_p": 0.95,
        },
    )


def init_models():
    global _summary_agent, _summary_all_agent, _solution_agent, _future_agent, _calendar_agent, _intent_agent
    
    # Force reinitialization every time to avoid tool binding issues
    # if (
    #     _summary_agent is not None
    #     and _summary_all_agent is not None
    #     and _solution_agent is not None
    #     and _future_agent is not None
    #     and _calendar_agent is not None
    # ):
    #     return

    _init_vertex()

    summary_tools = []
    summary_all_tools = [
        submit_incident_report
    ]

    calendar_tools = [
        list_events,
        create_event,
        check_availability,
        find_available_slots,
        add_user_to_channel,
        search_users_with_discord,
        schedule_discord_invite,       # Re-enabled after fixing type hints
        list_scheduled_invites,        # Re-enabled after fixing type hints
        cancel_scheduled_invite,       # Re-enabled after fixing type hints
        send_direct_message,           # Direct Message tool
        find_best_meeting_time,        # Find optimal meeting time for channel members
    ]
    
    print(f"DEBUG: calendar_tools count = {len(calendar_tools)}")
    print(f"DEBUG: calendar_tools = {[t.__name__ if hasattr(t, '__name__') else str(t) for t in calendar_tools]}")

    future_tools = [
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
        send_direct_message,           # Direct Message tool
    ]

    _summary_agent = _build_agent(summary_tools)
    _summary_all_agent = _build_agent(summary_all_tools)
    _solution_agent = _build_agent(solution_tools)
    _calendar_agent = _build_agent(calendar_tools)
    _future_agent = _build_agent(future_tools)
    _intent_agent = _build_agent([])


def _detect_intent(user_message: str) -> str:
    text = (user_message or "").lower()
    if any(keyword in text for keyword in ["結案報告", "事故結案", "post-mortem", "post mortem", "結案"]):
        return "summary_all"
    # Discord + Calendar 相關都用 calendar mode (因為 Discord tools 也在 calendar_agent 中)
    if any(keyword in text for keyword in ["行程", "日曆", "行事曆", "會議", "邀請", "空檔", "有空", "可用時間", "加進頻道", "加入頻道", "拉進來", "加入討論", "discord"]):
        return "calendar"
    if any(keyword in text for keyword in ["報案問題", "影響範圍"]):
        return "summary_problem"
    if any(keyword in text for keyword in ["如何改進", "未來改進", "改善", "提升", "預防", "防範", "改進"]):
        return "future_improve"
    if any(keyword in text for keyword in ["怎麼解決", "如何解決", "解決", "修復", "排除", "處理"]):
        return "solution"
    semantic_mode = _semantic_intent_fallback(text)
    if semantic_mode:
        return semantic_mode
    return "unknown"



def _semantic_intent_fallback(user_message: str) -> Optional[str]:
    if not user_message or not user_message.strip():
        return None
    if _intent_agent is None:
        init_agent_vertex()

    allowed_modes = {"summary_all", "summary_problem", "calendar", "future_improve", "solution"}
    intent_prompt = (
        "你是意圖分類器。請根據使用者輸入，從以下模式中選一個最適合的：\n"
        "- summary_all: 要求結案報告 / post-mortem\n"
        "- summary_problem: 要求統整報案問題與影響範圍\n"
        "- calendar: 查詢或安排日曆、會議、加人進 Discord 頻道、私訊或排程邀請\n"
        "- future_improve: 要求如何改善、預防、未來改進\n"
        "- solution: 問題排查、修復、處理、解法\n\n"
        "規則：\n"
        "1. 只能輸出單一模式字串，不要任何額外文字。\n"
        "2. 若完全沒有對應，請輸出 unknown。\n"
        "3. 否則輸出最相近的模式。\n\n"
        f"使用者輸入：{user_message}"
    )

    try:
        init_agent_vertex()
        response = _intent_agent.query(
            input={"messages": [("user", intent_prompt)]},
            config={"recursion_limit": 20},
        )
    except Exception as e:
        logger.warning(f"semantic_intent_fallback failed: {e}")
        return None

    mode_text = ""
    if isinstance(response, str):
        mode_text = response.strip().lower()
    elif isinstance(response, dict) and "messages" in response:
        for msg in reversed(response["messages"]):
            if msg.get("kwargs", {}).get("type") == "ai":
                mode_text = (msg.get("kwargs", {}).get("content") or "").strip().lower()
                if mode_text:
                    break
    else:
        mode_text = str(response).strip().lower()

    mode_text = mode_text.strip("` \n\r\t\"'")
    if not mode_text:
        return None
    mode_text = mode_text.split()[0]
    return mode_text if mode_text in allowed_modes else "unknown"


def _history_to_text(history: Optional[list[dict]]) -> str:
    if not history:
        return ""
    lines = []
    for item in history[-12:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_prompt(user_message: str, mode: str, history: str, rag_context: str, channel_id: Optional[int] = None) -> str:
    # Prepend system instruction to all prompts
    prompt_body = ""
    if mode == "summary_all":
        prompt_body = _build_summary_all_prompt(user_message, history, rag_context)
    elif mode == "summary_problem":
        prompt_body = _build_summary_prompt(user_message, history, rag_context)
    elif mode == "calendar":
        prompt_body = _build_calendar_prompt(user_message, history, rag_context, channel_id)
    elif mode == "future_improve":
        prompt_body = _build_future_prompt(user_message, history, rag_context)
    else:
        prompt_body = _build_solution_prompt(user_message, history, rag_context)
    
    return f"{SYSTEM_INSTRUCTION}\n\n{prompt_body}"


def _build_future_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "模式：未來改進（針對這次的問題提出對於程式碼的改進建議）\n"
        "建議先使用 Log/Code 工具查看系統內部的錯誤特徵或實作模式（搜尋 logs 或搜尋 code 找不當或可優化的寫法）\n"
        "如需外部資料，請參考以下官方或高可信來源：\n"
        "- docs.aws.amazon.com, aws.amazon.com, cloud.google.com\n"
        "- www.postgresql.org, www.cybertec-postgresql.com\n"
        "- man7.org, help.ubuntu.com, wiki.ubuntu.com, www.redhat.com, access.redhat.com, www.freedesktop.org\n"
        "- owasp.org, www.cisecurity.org, nvlpubs.nist.gov\n"
        "- sre.google, landing.google.com/sre, netflixtechblog.com, blog.cloudflare.com\n"
        "最後結合內部現狀與可查到的既有資料。\n"
        "請嚴格依照以下純文字的形式輸出，並且不要有格式限制以外的文字輸出\n\n"
        "## 之後如何避免\n"
        "- 未來預防措施\n"
        "格式範例：\n"
        "預防措施 1: (標題，是針對這次發生的問題具體可以預防的建議)\n\n"
        "內容: (清楚的提出完整的實施方法)\n"
        "負責人: (建議負責團隊，如 Infra Team, SRE Team, DevOps Team, Security Team, DBA Team)\n"
        "參考資料: (可填內部檔案或外部連結；若無請填 None)\n\n"
        "(請依序產出多個預防措施)\n\n"
        "- 其他隱藏的危險及優化方法\n"
        "請具體提出是因為哪個 Log 或 Code 有效率低下的寫法或錯誤用法，提出具體的潛在風險預警或優化建議\n"
        "並在下一行附上參考資料（內部檔案或外部連結；若無請填 None）\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_summary_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
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
    frontend_host = (settings.FRONTEND_HOST or "FRONTEND_HOST").strip()
    if frontend_host.startswith("http://") or frontend_host.startswith("https://"):
        case_url_template = f"{frontend_host.rstrip('/')}/cases/文件編號"
    else:
        case_url_template = f"http://{frontend_host.strip('/')}/cases/文件編號"
    return (
        "**執行步驟 (務必遵守)**：\n"
        "1. **生成回應**：請先根據整理好的資訊，**務必**將完整的 Markdown 報告內容輸出給使用者看。\n"
        f"   在結尾要提供 案件網址: {case_url_template}\n"
        "   請嚴格並務必依照下列格式輸出給使用者，不要用雙引號包住，不要加多餘文字，從對話紀錄找到相關內容務並內容都整理輸出，除了數字以外的分點都用點來表示，縮排務必整齊\n\n"
        "        \"tNote 系統事故結案報告 (Post-Mortem Report)\\n\\n\"\n"
        "        \"文件編號: (請依使用者@bot請求結案報告的日期與時間命名為 INC-YYYYMMDD-HHMM)\\n\"\n"
        "        \"報告日期: (若對話或資料有日期就使用，沒有請填未知)\\n\"\n"
        "        \"事件標題: (若對話或資料有標題就使用，沒有請填未知)\\n\\n\"\n"
        "        \"1. 基本資訊\\n\\n\"\n"
        "        \"Issue 發生時間: (若對話或資料有時間就使用，沒有請填未知)\\n\\n\"\n"
        "        \"Issue 解決時間: (請使用使用者@bot提出結案報告需求的時間)\\n\\n\"\n"
        "        \"事件等級: (若對話或資料有等級就使用，沒有請依下列標準判斷)\\n\"\n"
        "        \"(以下是參考的分級標準不印出)\"\n"
        "        \"P0: 全站/核心服務不可用或大規模資料風險\\n\"\n"
        "        \"P1: 主要功能不可用或大量使用者受影響\\n\"\n"
        "        \"P2: 部分功能異常或有限使用者受影響\\n\"\n"
        "        \"P3: 輕微問題或體驗/效能影響\\n\\n\"\n"
        "        \"(以上是參考的分級標準不印出)\"\n"
        "        \"2. 報案問題\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"3. 影響範圍\\n\\n\"\n"
        "        \"- 服務影響\\n\\n\"\n"
        "        \"- 使用者影響\\n\\n\"\n"
        "        \"- 資料影響\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"4. Issue 發生細節描述\\n\\n\"\n"
        "        \"- 根本原因\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"- 事件細節\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"- 事件時間軸\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"- 檔案閱讀推理過程\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"5. 解決方案\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"6. 之後如何避免\\n\\n\"\n"
        "        \"- 未來預防措施\\n\\n\"\n"
        "        \"預防措施 X: (標題，是針對這次發生的問題具體可以預防的建議)\\n\\n\"\n"
        "        \"內容: (清楚的提出完整的實施方法)\\n\"\n"
        "        \"負責人: (建議負責團隊，如 Infra Team, SRE Team, DevOps Team, Security Team, DBA Team)\\n\"\n"
        "        \"參考連結: (請一定要附上找到的參考連結)\\n\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"- 其他隱藏的危險及優化方法\\n\\n\"\n"
        "        \"請具體提出是因為哪個 Log 或 Code 有效率低下的寫法或錯誤用法，提出具體的潛在風險預警或優化建議\\n\"\n"
        "        \"並在下一行一定要附上找到的參考連結\\n\"\n"
        "        \"(若對話紀錄已有該段落內容，直接原文引用或等義整理；沒有則補齊。)\\n\\n\"\n"
        "        \"注意：優先使用對話紀錄中的既有內容；只有缺少時才補寫。\"\n\n"

        "2. **呼叫工具**：輸出完報告後，緊接著**根據上述產生的報告內容**，將對應的資訊提取出來，呼叫 `submit_incident_report` 工具將結構化資料存入資料庫。\n"
        "   - `filename`: 對應「文件編號」 (e.g. INC-20230910-1030)\n"
        "   - `report_date`: 對應「報告日期」，若未知請填 None\n"
        "   - `occurred_at`: 對應「Issue 發生時間」，若未知請填 None\n"
        "   - `resolved_at`: 對應「Issue 解決時間」，請轉換為 ISO 格式\n"
        "   - `title`: 對應「事件標題」\n"
        "   - `severity`: 對應「事件等級」\n"
        "   - `report_problem`: 對應「報案問題」\n"
        "   - `impact_service`: 對應「影響範圍 - 服務影響」\n"
        "   - `impact_user`: 對應「影響範圍 - 使用者影響」\n"
        "   - `impact_data`: 對應「影響範圍 - 資料影響」\n"
        "   - `root_cause`: 對應「根本原因」\n"
        "   - `event_details`: 對應「事件細節」\n"
        "   - `timeline`: 對應「事件時間軸」，轉為 list of strings\n"
        "   - `inference_process`: 對應「檔案閱讀推理過程」\n"
        "   - `solution`: 對應「解決方案」\n"
        "   - `preventive_measures`: 將「未來預防措施」轉為 List of Dict (必須包含 `title`, `content`, `owner`, `link`)\n"
        "   - `hidden_risks`: 將「隱藏的危險及優化方法」轉為 List of Dict (必須包含 `title`, `content`, `link`)\n\n"
        "請務必回覆內容，不要省略任何區塊。\n"
        "存入資料庫時請將上述內容轉為對應的參數格式。\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_calendar_prompt(user_message: str, history: str, rag_context: str, channel_id: Optional[int] = None) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(tz)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    current_channel_info = f"當前 Discord 頻道 ID: {channel_id}" if channel_id else "當前 Discord 頻道 ID: 未知 (請詢問使用者)"

    return (
        "你是一個**緊急狀況會議助手**。\\n"
        "你的回應必須**簡要、精準、專業**，只需記錄完成的動作，不要冗長說明。\\n\\n"
        "**回應格式範例**：\\n"
        "✅ 已查詢到 ivan 下一個有空時間並通知 ivan，將在 2026-02-07 14:30 時將 ivan 加入頻道\\n"
        "✅ 根據排程已將 ivan 加入頻道\\n"
        "✅ 已將 Kevin 加入頻道並通知\\n"
        "✅ 建議會議時間：2026-02-10 15:00-16:00，全員可參與\\n\\n"
        "**禁止輸出**：\\n"
        "❌ 不要輸出工具呼叫的詳細參數\\n"
        "❌ 不要輸出過程中的思考步驟\\n"
        "❌ 不要輸出 JSON 或技術細節\\n"
        "❌ 不要說「我現在要...」、「讓我...」等過程描述\\n\\n"
        "---\\n\\n"
        "模式：calendar（查詢/安排日曆）。\\n"
        "所在時區：Asia/Taipei (GMT+8)\\n"
        f"現在時間是：{now_str} (請以此時間為基準推斷「現在」、「這週」等相對日期)\\n"
        f"{current_channel_info}\\n"
        "注意：如果外部工具回傳 UTC 時間 (例如結尾為 Z 的時間)，請務必將其轉換為 GMT+8 後再回答使用者。\\n\\n"
        "**🔴 重要規則（必須遵守）**\\n"
        "1. **當新增背景 scheduler 事件時**，必須使用 `send_direct_message` 發送訊息給當事人，告知已為他建立排程。\\n"
        "2. **當新增人至 Discord 頻道時**，必須使用 `send_discord_message` 在頻道中 @ 當事人，告知已將他加入。\\n\\n"
        "**日曆助手進階策略：**\\n\\n"
        "**重要：Atomic Logic (分步執行)**\\n"
        "- 請根據需求**分步驟**呼叫對應的工具。\\n"
        "- `check_availability` 僅負責檢查時間，**不會**自動加人或建會議。\\n"
        "- **所有 ID (channel_id, discord_id) 必須使用字串格式**，避免精度丟失。\\n\\n"
        "1. **緊急找人 (Mobilize)**：\n"
        "   - 「Ivan 在嗎？拉 Ivan 進來」\n"
        "   - 步驟一：呼叫 `check_availability` 檢查是否有空。\n"
        "   - 步驟二：如果回傳結果顯示 Available (或你判斷可打擾)，再呼叫 `add_user_to_channel(name, channel_id='...')`。\n\n"
        "2. **建立 War Room (Emergency Sync)**：\n"
        "   - 「緊急會議」、「War Room」\n"
        "   - 步驟一：呼叫 `check_availability` 確保大家有空。\n"
        "   - 步驟二：呼叫 `create_calendar_event` 建立會議。\n"
        "   - 步驟三：呼叫 `send_discord_message(channel_id='...', message='...')` 通知大家會議連結。\n\n"
        "3. **Discord 邀請**：\n"
        "   - 「把 Kevin 加進頻道」\n"
        "   - 如果沒有特別說要看時間，可以直接呼叫 `add_user_to_channel(name, channel_id='...')`。\n"
        "   - **重要：加人之後，必須用 `send_discord_message` 發訊息通知當事人**。\n"
        "   - 訊息範例：「@Kevin 已將你加入頻道，有事情需要討論」\n"
        "   - 如果說「如果有空才加」，請先 Check 再 Add。\n\n"
        "4. **排程邀請 (Scheduled Invite)**：\n"
        "   - 「等 Kevin 有空把他拉進來」\n"
        "   - **⚡ 智慧判斷邏輯**：\n"
        "     1. 先呼叫 `check_availability` 查詢當前是否有空\n"
        "     2. 如果 `available: true` (現在有空) → **直接呼叫 `add_user_to_channel` + `send_discord_message` 通知**\n"
        "     3. 如果 `available: false` (現在沒空) → 呼叫 `schedule_discord_invite` 排程到下一個有空時段\n"
        "        **然後立即呼叫 `send_direct_message` 通知當事人已為他建立排程**\n"
        "   - **重要**：\n"
        "     - 排程時 `notification_message` 參數必須填寫，範例：「Hi Kevin，會議準備開始了，請過來一下！」\n"
        "     - 建立排程後，必須用 DM 通知當事人，範例：「Hi Kevin，目前你在忙，已為你排程在 15:00 將你加入會議頻道」\n"
        "   - 回應範例：\n"
        "     - 現在有空：「✅ Kevin 目前有空，已將他加入頻道並通知」\n"
        "     - 現在沒空：「✅ Kevin 目前忙碌中，已排程在 2026-02-07 15:00 將他加入頻道，並已私訊通知」\n\n"
        "5. **私訊通知 (Direct Message)**：\n"
        "   - 「如果他沒空就私訊跟他講一聲」\n"
        "   - 使用 `send_direct_message(user_name, message)`。\n"
        "   - 訊息範例：「Hi Kevin，原定要拉你進會議，但看你目前有行程，麻煩忙完後進頻道一下，謝謝。」\n\n"
        "6. **找最佳會議時間 (Best Meeting Time)**：\n"
        "   - 「找這週大家都有空的時間」、「約這週最多人能參加的時間」\n"
        "   - 使用 `find_best_meeting_time(channel_id, time_min, time_max)`。\n"
        "   - 參數範例：\n"
        "     - channel_id: 當前頻道 ID (從 context 取得)\n"
        "     - time_min: \"2026-02-10T00:00:00Z\" (本週一早上)\n"
        "     - time_max: \"2026-02-16T23:59:59Z\" (本週日晚上)\n"
        "   - 這個工具會返回所有頻道成員的日曆忙碌時段。\n"
        "   - **你的任務**：分析這些忙碌時段，找出：\n"
        "     1. 所有人都有空的時段（最優先）\n"
        "     2. 如果沒有，找最多人有空的時段\n"
        "   - 回覆格式：「建議時間：2026-02-12 14:00-15:00，全員/80%參與」\n\n"
        "7. **事後檢討 (Post-Mortem)**：\n"
        "   - 「約檢討會」\n"
        "   - 使用 `check_availability` 查詢並透過回傳的參數尋找空檔。\n"
        "\n歷史對話:\n"
        f"{history}\n"
        "\n參考資料:\n"
        f"{rag_context}\n"
        "\n使用者輸入:\n"
        f"{user_message}\n"
    )


def _build_solution_prompt(user_message: str, history: str, rag_context: str) -> str:
    return (
        "模式：solution（協助解決問題，務必交叉查閱對log、code、結案報告，在每一次的查閱中找到下一次要看的檔案並使用函式，務必這四種每一種調閱都要試過）\n"
        "請一次完成並輸出最終結果，只輸出兩段(回復不能為空非常重要)，不要輸出底下括號內的文字，務必不能查看重複的檔案超過兩次\n"
        "## Issue 發生細節描述\n"
        "- 根本原因(用一兩句話總結整個問題)\n"
        "- 事件時間軸(詳細寫出在每個開過的檔案中的推理，逐條列出什麼時間點發生甚麼)\n"
        "- 檔案閱讀推理過程(詳細寫說是在code, log中看到什麼才決定打開什麼檔案並在其中搜尋甚麼發現甚麼)\n"
        "推理過程範例，根據使用者提到什麼的對話決定先去看甚麼log或code。之後繼續列在該份log和code中發現了什麼，才決定接下來要看什麼檔案。務必列出詳細的推理過程，並且在每個步驟都標明參考的檔案名稱和內容摘要。\n"
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
    channel_id: Optional[int] = None,
) -> dict:
    init_models()

    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    resolved_mode = mode or _detect_intent(user_message)
    logger.info(f"run_agent intent resolved_mode={resolved_mode}")
    
    if resolved_mode == "unknown":
        return {
            "message": (
                "我不太確定你要的模式。你可以用更明確的指令：\n"
                "- 結案報告: 「請產出結案報告 / post-mortem」\n"
                "- 日曆/Discord: 「幫我安排會議 / 查空檔 / 把人加進頻道」\n"
                "- 報案問題: 「統整報案問題與影響範圍」\n"
                "- 未來改進: 「如何改進 / 預防措施」\n"
                "- 解決方案: 「如何解決 / 排除 / 修復」"
            ),
            "structured": None,
            "mode": resolved_mode,
            "confidence": 0.0,
        }
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
        channel_id=channel_id,
    )
    prompt = f"{SYSTEM_INSTRUCTION}\n\n{prompt}"

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

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

import requests
from sqlalchemy import desc, func, or_

from app.database import SessionLocal
from app.models import Code, Knowledge, LogEntry, LogFile
from app.config import settings
from app.services.message_service import list_recent_messages, search_messages


_progress_sender: Optional[Callable[[str], None]] = None


def set_progress_sender(sender: Optional[Callable[[str], None]]) -> None:
    global _progress_sender
    _progress_sender = sender



def _emit_progress(message: str) -> None:
    if not _progress_sender:
        return
    try:
        _progress_sender(message)
    except Exception:
        return




def _format_timestamp(value: Optional[datetime]) -> str:
    if not value:
        return "-"
    return value.isoformat(sep=" ", timespec="seconds")


def _format_message_line(item) -> str:
    ts = _format_timestamp(getattr(item, "timestamp", None))
    user = getattr(item, "user", None) or "Unknown"
    role = getattr(item, "role", None) or ""
    role_text = f" ({role})" if role else ""
    content = (getattr(item, "content", None) or "").strip()
    if len(content) > 200:
        content = content[:200] + "..."
    return f"[{ts}] {user}{role_text}: {content}"


def _preface(source: str, reason: str) -> str:
    return f"目前在看: {source}\n原因: {reason}\n"


def list_recent_discord_messages(limit: int = 20) -> str:
    """
    List recent Discord messages stored in the database.
    Use this to understand recent conversation context.
    """
    items = list_recent_messages(limit=limit)
    if not items:
        return "沒有可用的 Discord 對話紀錄。"
    lines = ["最近的 Discord 對話紀錄:"]
    lines.extend(_format_message_line(item) for item in items)
    return "\n".join(lines)


def search_discord_messages(query: str, limit: int = 20) -> str:
    """
    Search Discord messages by keyword.
    Use this to find relevant discussions or context.
    """
    items = search_messages(query=query, limit=limit)
    if not items:
        return "找不到相關的 Discord 對話紀錄。"
    lines = [f"Discord 對話搜尋結果 (query={query}):"]
    lines.extend(_format_message_line(item) for item in items)
    return "\n".join(lines)


def search_industry_standards(query: str, limit: int = 5) -> str:
    """
    使用 Google Custom Search 查詢業界標準/最佳實務（例如 CI/CD 工具、Security Linters）。

    需要設定 GOOGLE_SEARCH_CREDENTIALS_PATH 指向包含 api_key 與 cx 的 JSON 檔案。
    """
    if not query or not query.strip():
        return "請提供要搜尋的關鍵字 (例如: CI/CD best practices, security linters)。"

    api_key = settings.GOOGLE_SEARCH_API_KEY
    cx = settings.GOOGLE_SEARCH_CX

    # 嘗試從 JSON 檔案讀取 (如果有的話)
    if settings.GOOGLE_SEARCH_CREDENTIALS_PATH:
        try:
            import json
            p = Path(settings.GOOGLE_SEARCH_CREDENTIALS_PATH)
            if not p.is_absolute():
                p = Path(settings.BACKEND_ROOT) / settings.GOOGLE_SEARCH_CREDENTIALS_PATH
            
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    creds = json.load(f)
                    api_key = creds.get("api_key") or api_key
                    cx = creds.get("cx") or cx
        except Exception as e:
            return f"讀取搜尋憑證失敗: {e}"

    if not api_key or not cx:
        return (
            "尚未設定 Google 搜尋金鑰/自訂搜尋引擎 (GOOGLE_SEARCH_API_KEY, GOOGLE_SEARCH_CX 或 search_credentials.json)，"
            "請補齊設定後再試。"
        )

    limit = max(1, min(limit, 10))
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": limit,
        "safe": "active",
    }

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return f"Google 搜尋失敗: {exc}"

    items = data.get("items") or []
    if not items:
        return "Google 搜尋沒有找到相關結果。"

    lines = [f"Google 搜尋結果 (top {limit}, query={query}):"]
    for item in items[:limit]:
        title = item.get("title") or "未命名結果"
        link = item.get("link") or ""
        snippet = (item.get("snippet") or "").replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        lines.append(f"- {title}: {link} — {snippet}")
    return "\n".join(lines)


def analyze_risk_mitigation(context: str, stack: str | None = None, hint: str | None = None) -> str:
    """
    根據錯誤/警告/stack 文字，給出隱藏風險 + 避免方式 + 效率提升建議。

    輸入：
      - context: 錯誤訊息或 log 片段
      - stack: （可選）堆疊或額外線索
      - hint:  （可選）模組/服務名稱或場景描述
    輸出：條列的風險/預防/效率建議。
    """
    if not context or not context.strip():
        return "沒有提供內容，無法分析。請附上錯誤訊息或 log 片段。"

    text = f"{context}\n{stack or ''}\n{hint or ''}".lower()
    findings = []

    def add(msg: str):
        findings.append(f"- {msg}")

    # 分類規則：網路 / 連線池 / 資料庫 / 儲存 / 權限 / 資源 / 併發 / 部署 / 相依服務 / 鎖 / 排程 / TLS-DNS
    if any(k in text for k in ["timeout", "timed out", "latency", "slow query", "ssl handshake", "dns"]):
        add("網路/延遲風險：缺乏超時與重試；DNS/TLS 問題也會表現為 timeout。預防：設定 per-call timeout、指數退避重試、DNS/TLS 健康檢查與快取。效率：對頻繁請求做快取/批次化，減少往返。")
    if any(k in text for k in ["connection", "connect", "refused", "connection pool", "too many clients", "max_connections"]):
        add("連線池耗盡/連不上：可能是池參數過小、泄漏或暴衝。預防：設置上限與閒置回收、追蹤池使用率、對 burst 加入排隊/熔斷。")
    if any(k in text for k in ["replica", "replication", "wal", "lag", "read replica", "replication delay"]):
        add("複寫延遲/中斷：讀寫不一致風險。預防：對強一致需求走主庫或 sync read、設延遲告警、定期驗證複寫健康。")
    if any(k in text for k in ["deadlock", "lock wait", "serialization", "row lock", "table lock"]):
        add("鎖衝突/死鎖：交易設計或長查詢造成。預防：縮短交易、減少鎖範圍、改用批次/樂觀鎖、加索引降低掃描。")
    if any(k in text for k in ["disk full", "no space", "quota", "readonly file system"]):
        add("儲存/磁碟空間：磁碟滿會導致寫入失敗。預防：容量告警、日誌輪轉、冷/熱存分層、備援儲存。")
    if any(k in text for k in ["s3", "bucket", "upload", "storage", "permission denied", "403", "forbidden", "unauthorized"]):
        add("物件儲存/權限：ACL/憑證/角色漂移。預防：最小權限基線、憑證輪替監控、4xx/5xx 分流告警、重試佇列。")
    if any(k in text for k in ["oom", "out of memory", "memory", "heap", "cpu", "loadavg"]):
        add("資源水位：可能 OOM 或 CPU 飆高。預防：資源告警、HPA/自動伸縮、限制單請求記憶體、做壓測與容量規劃。效率：熱路徑快取與拆分高耗作業。")
    if any(k in text for k in ["gc", "garbage", "stop the world", "paused"]):
        add("GC 暫停：heap 過大或物件爆量。預防：調 GC 參數、降低暫存物件、分批處理。")
    if any(k in text for k in ["race", "concurrent", "thread", "goroutine", "async", "mutex"]):
        add("併發風險：競態/鎖保護不足。預防：確保臨界區鎖定、使用原子操作/immutable 資料、加測試覆蓋。")
    if any(k in text for k in ["queue", "kafka", "lag", "backlog", "offset"]):
        add("訊息佇列延遲/堆積：消費速率不足或訂閱故障。預防：監控 lag、彈性擴容消費者、死信與重試通道。")
    if any(k in text for k in ["deploy", "rollout", "migration", "schema", "migrate", "ddl"]):
        add("部署/遷移風險：版本/模式不相容。預防：向後相容 rollout、分階段釋出、DB migration 前後健康檢查。效率：自動化 smoke test。")
    if any(k in text for k in ["tls", "certificate", "cert", "expired", "ssl"]):
        add("TLS 憑證：過期或信任鏈問題。預防：憑證到期告警、自動輪替、雙向 TLS 時同步更新信任鏈。")
    if any(k in text for k in ["cache", "redis", "ttl", "evict", "miss"]):
        add("快取風險：快取雪崩/失效。預防：設定 TTL 抖動、熱 key 保護、回源熔斷、預熱。")
    if any(k in text for k in ["retry", "circuit", "breaker", "throttle", "rate limit"]):
        add("穩定性機制：缺乏或設定不當。預防：正確的重試策略(限 idempotent)、熔斷與速率限制、退避策略。")

    if not findings:
        add(
            "通用建議：\n"
            " 1) 超時 + 指數退避重試 + 熔斷/限流；\n"
            " 2) 權限/憑證健康檢查與輪替監控；\n"
            " 3) DB/複寫/佇列健康度監控與延遲告警；\n"
            " 4) 資源水位告警 + 壓測/容量規劃；\n"
            " 5) 部署/遷移前後的 smoke test 與回滾計畫；\n"
            " 6) 記錄並追蹤錯誤率/延遲/飽和度四大黃金訊號。"
        )

    return "\n".join(findings)


def propose_process_improvements(context: str | None = None) -> str:
    """
    提出超越程式碼修改的流程性建議，聚焦預防高風險變更與提升效率。
    可搭配錯誤背景 (context) 使用，但非必填。
    """
    base = [
        "AI 隱私/圍欄: 確保 RAG 檢索時嚴格執行權限過濾 (ACL filtering)，防止 AI 引用使用者無權限的筆記內容作為回答來源。",
        "檔案上傳安全: 對所有上傳檔案 (PDF, Office) 執行掃毒與格式清洗 (Sanitization)，防止惡意 payload 攻擊解析器或導致前端 XSS。",
        "向量庫效能: 針對高頻更新的筆記建立延遲索引或增量更新機制 (Incremental Indexing)，避免 re-index 造成檢索暫時失效。",
        "AI 幻覺與正確性: 建立使用者回饋機制 (Thumbs up/down)，並定期評估 Chatbot 回答準確率；對高風險回答加入引用來源標示強制性。",
        "資源配額管理: 對單一使用者的上傳量、OCR 頁數、AI Token 消耗設定 Rate Limit 與 Quota，防止單一租戶耗盡系統資源。",
        "資料隔離: 確保不同筆記本/組織間的資料邏輯或物理隔離，特別是當 AI Context 混合檢索時，需防止跨租戶資料洩露。",
        "敏感資料遮罩: 在送往 LLM 前，自動偵測並遮罩 PII (個人識別資訊) 或機敏關鍵字，避免將機密資料傳送至外部模型供應商。",
        "版本控制與還原: 為筆記內容提供版控，當 AI 錯誤修改或是使用者誤刪時，可快速回滾至先前的版本。",
    ]

    if context and context.strip():
        return "超越性流程建議:\n" + "\n".join(f"- {item}" for item in base) + "\n(依錯誤背景補充) " + context.strip()
    return "超越性流程建議:\n" + "\n".join(f"- {item}" for item in base)


def analyze_risk_mitigation(context: str) -> str:
    """
    根據錯誤或警告文字，提出隱藏風險與預防/效率建議。
    輸入: 任意錯誤訊息、事件摘要、log 片段。
    """
    if not context or not context.strip():
        return "沒有提供內容，無法分析。"

    text = context.lower()
    findings = []
    if any(k in text for k in ["timeout", "timed out", "latency"]):
        findings.append("可能的隱藏風險: 網路/IO 延遲未設重試，流量高峰會放大。預防: 指數退避重試、逾時與錯誤率告警；效率: 熱路徑快取或批次化。")
    if any(k in text for k in ["permission", "denied", "forbidden", "unauthorized"]):
        findings.append("可能的隱藏風險: 權限漂移或憑證過期。預防: 追蹤憑證輪替、最小權限基線、定期權限健康檢查。")
    if any(k in text for k in ["replica", "replication", "wal", "lag"]):
        findings.append("可能的隱藏風險: 資料庫複寫延遲/中斷導致讀寫不一致。預防: 設複寫延遲告警、關鍵讀走主庫或強一致、週期性驗證複寫健康。")
    if any(k in text for k in ["upload", "storage", "s3", "bucket"]):
        findings.append("可能的隱藏風險: 儲存策略/ACL 變更或區域事件。預防: 區分 4xx/5xx 告警、檢查桶策略/KMS 權限、提供暫存重試佇列。")
    if any(k in text for k in ["connection", "connect", "refused"]):
        findings.append("可能的隱藏風險: 連線池耗盡或防火牆變更。預防: 監控連線池水位、設定 max_connections 與閒置清理、持續驗證防火牆規則。")
    if any(k in text for k in ["memory", "oom", "cpu", "load"]):
        findings.append("可能的隱藏風險: 資源突增導致崩潰/節流。預防: HPA/自動伸縮、資源水位告警、壓測與容量基準。")

    if not findings:
        findings.append("未偵測到特定關鍵字，請提供更完整的錯誤/警告片段以精準分析。通用預防: 重試+超時、權限與憑證健康檢查、複寫/備援監控、資源水位告警與容量規劃。")

    return "\n".join(f"- {f}" for f in findings)


def list_log_files(limit: int = 20) -> str:
    """
    List available log files in the database.
    """
    _emit_progress("目前在看: log 檔案清單")
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        rows = db.query(LogFile).order_by(LogFile.filename.asc()).limit(limit).all()
        if not rows:
            return "目前沒有任何 log 檔案。"
        lines = ["可用的 log 檔案:"]
        lines.extend(f"- {row.filename}" for row in rows)
        return "\n".join(lines)
    finally:
        db.close()


def search_log_entries(query: str, file_name: Optional[str] = None, limit: int = 30) -> str:
    """
    Search log entries by keyword, optionally within a specific file.
    """
    source = f"log: {file_name or 'all'}"
    _emit_progress(f"目前在看: {source}\n原因: 搜尋 log 關鍵字 {query}")
    limit = max(1, min(limit, 100))
    if not query:
        return "請提供要搜尋的 log 關鍵字。"
    db = SessionLocal()
    try:
        q = f"%{query.strip().lower()}%"
        base = db.query(LogEntry, LogFile).join(LogFile, LogEntry.file_id == LogFile.id)
        if file_name:
            base = base.filter(func.lower(LogFile.filename) == file_name.strip().lower())
        rows = (
            base.filter(func.lower(LogEntry.raw_content).like(q))
            .order_by(desc(LogEntry.timestep), desc(LogEntry.id))
            .limit(limit)
            .all()
        )
        if not rows:
            return "找不到符合條件的 log。"
        lines = ["Log 搜尋結果:"]
        for entry, logfile in rows:
            ts = _format_timestamp(entry.timestep)
            snippet = entry.raw_content
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."
            lines.append(
                f"[{logfile.filename}#{entry.line_number} {ts}] {snippet}"
            )
        return "\n".join(lines)
    finally:
        db.close()


def list_code_files(limit: int = 50) -> str:
    """
    List available code files in the database.
    """
    _emit_progress("目前在看: code 檔案清單")
    limit = max(1, min(limit, 200))
    db = SessionLocal()
    try:
        rows = db.query(Code).order_by(Code.filename.asc()).limit(limit).all()
        if not rows:
            return "目前沒有任何 code 索引資料。"
        lines = ["可用的 code 檔案:"]
        lines.extend(f"- {row.filename}" for row in rows)
        return "\n".join(lines)
    finally:
        db.close()


def _build_snippet(content: str, query: str, max_chars: int = 240) -> str:
    if not content:
        return ""
    q = query.strip().lower()
    idx = content.lower().find(q)
    if idx == -1:
        return content[:max_chars] + ("..." if len(content) > max_chars else "")
    start = max(0, idx - 60)
    end = min(len(content), idx + 60)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return snippet.replace("\n", " ")


def search_code_snippets(query: str, limit: int = 5) -> str:
    """
    Search code snippets by keyword.
    """
    _emit_progress(f"目前在看: code 搜尋\n原因: 搜尋程式碼關鍵字 {query}")
    limit = max(1, min(limit, 20))
    if not query:
        return "請提供要搜尋的 code 關鍵字。"
    db = SessionLocal()
    try:
        q = f"%{query.strip().lower()}%"
        rows = (
            db.query(Code)
            .filter(func.lower(Code.content).like(q))
            .order_by(Code.filename.asc())
            .limit(limit)
            .all()
        )
        if not rows:
            return "找不到符合條件的 code。"
        lines = [f"Code 搜尋結果 (query={query}):"]
        for row in rows:
            snippet = _build_snippet(row.content or "", query)
            lines.append(f"- {row.filename}: {snippet}")
        return "\n".join(lines)
    finally:
        db.close()


def get_code_file(filename: str, max_chars: int = 3000) -> str:
    """
    Retrieve a code file content by filename.
    """
    _emit_progress(f"目前在看: code {filename}\n原因: 讀取檔案內容以確認實作細節")
    if not filename:
        return "請提供要讀取的檔名。"
    db = SessionLocal()
    try:
        row = (
            db.query(Code)
            .filter(func.lower(Code.filename) == filename.strip().lower())
            .first()
        )
        if not row:
            return "找不到指定的 code 檔案。"
        content = row.content or ""
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... (內容已截斷)"
        return f"檔名: {row.filename}\n{content}"
    finally:
        db.close()


def list_case_reports(limit: int = 20) -> str:
    """
    List available incident reports (knowledge cases).
    """
    _emit_progress("目前在看: 結案報告清單")
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        rows = (
            db.query(Knowledge)
            .filter(Knowledge.root_cause.isnot(None))
            .order_by(Knowledge.case_id.asc())
            .limit(limit)
            .all()
        )
        if not rows:
            return "目前沒有任何結案報告。"
        lines = ["可用的結案報告:"]
        for row in rows:
            lines.append(
                f"- {row.case_id}: {row.title} (severity={row.severity})"
            )
        return "\n".join(lines)
    finally:
        db.close()


def get_case_report(case_id: str) -> str:
    """
    Retrieve a specific incident report by case ID.
    """
    _emit_progress(f"目前在看: 結案報告 {case_id}\n原因: 比對過去案例找出相似根因")
    if not case_id:
        return "請提供要查詢的 case_id。"
    db = SessionLocal()
    try:
        row = db.query(Knowledge).filter(Knowledge.case_id == case_id).first()
        if not row:
            return "找不到指定的結案報告。"
        return (
            f"Case {row.case_id}: {row.title}\n"
            f"Severity: {row.severity}\n"
            f"Summary: {row.summary}\n"
            f"Root Cause: {row.root_cause}\n"
            f"Immediate Fix: {row.immediate_fix}\n"
            f"Long-term Fix: {row.long_term_fix}\n"
        )
    finally:
        db.close()

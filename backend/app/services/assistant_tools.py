from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional
from pathlib import Path

import requests
from sqlalchemy import desc, func, or_

from app.database import SessionLocal
from app.models import Code, Knowledge, LogEntry, LogFile
from app.config import settings
from app.services.message_service import list_recent_messages, search_messages
from app.services.cases_service import save_case_report_structured

# Updated to use cases_service.save_case_report_structured
from app.services.cases_service import save_case_report_structured

def submit_incident_report(
    title: str,
    severity: str,
    root_cause: str,
    timeline: list[str],
    solution: str,
    
    # New Structured Fields
    filename: str = None, # User-facing ID (e.g. INC-2026...)
    report_date: str = None,
    occurred_at: str = None,
    resolved_at: str = None,
    report_problem: str = None,
    impact_service: str = None,
    impact_user: str = None,
    impact_data: str = None,
    event_details: str = None,
    inference_process: str = None,
    preventive_measures: list[dict] = [],
    hidden_risks: list[dict] = [], # JSON structure or List
) -> str:
    """
    Submit a finalized Incident Post-Mortem report to the database.
    
    Args:
        title: The title of the incident
        severity: One of 'critical', 'high', 'medium', 'low'
        root_cause: The fundamental cause
        timeline: List of timestamped events (strings)
        solution: Full solution description (Immediate + Long term)
        
        report_date: ISO 8601 date string (e.g. "2026-02-06T12:00:00")
        occurred_at: When the issue started (ISO 8601)
        resolved_at: When the issue was resolved (ISO 8601)
        report_problem: Description of the initial report
        impact_service: Service impact description
        impact_user: User impact description
        impact_data: Data impact description
        event_details: Detailed event log analysis
        inference_process: Reasoning steps
        preventive_measures: List of {title, content, owner, link}
        hidden_risks: List of {title, content, link} or structured risk objects
    """
    _emit_progress(f"正在將結案報告存入資料庫: {title}")
    
    data = {
        "title": title,
        "severity": severity,
        "root_cause": root_cause,
        "timeline": timeline,
        "solution": solution,
        "solution": solution,
        
        "filename": filename,
        "report_date": report_date,
        "occurred_at": occurred_at,
        "resolved_at": resolved_at,
        "report_problem": report_problem,
        "impact_service": impact_service,
        "impact_user": impact_user,
        "impact_data": impact_data,
        "event_details": event_details,
        "inference_process": inference_process,
        "preventive_measures": preventive_measures,
        "hidden_risks": hidden_risks,
    }
    
    try:
        case_id = save_case_report_structured(data)
        return f"報告已成功存檔。檔案名稱: {case_id}"
    except Exception as e:
        return f"存檔失敗: {str(e)}"


_progress_sender: Optional[Callable[[str], None]] = None
_log_context_channel_id: Optional[int] = None


def set_progress_sender(sender: Optional[Callable[[str], None]]) -> None:
    global _progress_sender
    _progress_sender = sender


def set_log_context(channel_id: Optional[int]) -> None:
    global _log_context_channel_id
    _log_context_channel_id = channel_id



def _emit_progress(message: str) -> None:
    if not _progress_sender:
        return
    try:
        _progress_sender(message)
    except Exception:
        return


def _log_scenario_filter() -> Optional[int]:
    if _log_context_channel_id is None:
        return None
    mapping: dict[int, int] = {}
    if settings.DISCORD_CHANNEL_ID_1:
        mapping[int(settings.DISCORD_CHANNEL_ID_1)] = 1
    if settings.DISCORD_CHANNEL_ID_2:
        mapping[int(settings.DISCORD_CHANNEL_ID_2)] = 2
    if settings.DISCORD_CHANNEL_ID_3:
        mapping[int(settings.DISCORD_CHANNEL_ID_3)] = 3
    scenario = mapping.get(int(_log_context_channel_id))
    if scenario is None:
        return -1
    return scenario


def _message_scenario_filter() -> Optional[int]:
    return _log_scenario_filter()




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
    scenario_filter = _message_scenario_filter()
    if scenario_filter is None:
        return "未提供 channel context，無法讀取 Discord 對話紀錄。"
    if scenario_filter == -1:
        return "channel id 未對應任何 scenario，無法讀取 Discord 對話紀錄。"
    items = list_recent_messages(limit=limit, scenario=scenario_filter)
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
    scenario_filter = _message_scenario_filter()
    if scenario_filter is None:
        return "未提供 channel context，無法搜尋 Discord 對話紀錄。"
    if scenario_filter == -1:
        return "channel id 未對應任何 scenario，無法搜尋 Discord 對話紀錄。"
    items = search_messages(query=query, limit=limit, scenario=scenario_filter)
    if not items:
        return "找不到相關的 Discord 對話紀錄。"
    lines = [f"Discord 對話搜尋結果 (query={query}):"]
    lines.extend(_format_message_line(item) for item in items)
    return "\n".join(lines)


def list_log_files(limit: int = 20) -> str:
    """
    List available log files in the database.
    """
    _emit_progress("目前在看: log 檔案清單")
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        rows = db.query(LogFile).order_by(LogFile.scenario.asc(), LogFile.filename.asc()).all()
        if not rows:
            return "目前沒有任何 log 檔案。"
        scenario_filter = _log_scenario_filter()
        if scenario_filter is None:
            return "未提供 channel context，無法讀取 log 檔案。"
        if scenario_filter == -1:
            return "channel id 未對應任何 scenario，無法讀取 log 檔案。"
        if scenario_filter is not None:
            rows = [row for row in rows if row.scenario == scenario_filter]
        rows = rows[:limit]
        if not rows:
            return "目前沒有任何 log 檔案。"
        lines = ["可用的 log 檔案:"]
        lines.extend(f"- Scenario{row.scenario or '-'}: {row.filename}" for row in rows)
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
        scenario_filter = _log_scenario_filter()
        if scenario_filter is None:
            return "未提供 channel context，無法搜尋 log。"
        if scenario_filter == -1:
            return "channel id 未對應任何 scenario，無法搜尋 log。"
        if scenario_filter is not None:
            base = base.filter(LogFile.scenario == scenario_filter)
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
                f"[Scenario{logfile.scenario or '-'}"
                f":{logfile.filename}#{entry.line_number} {ts}] {snippet}"
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

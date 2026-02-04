from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from sqlalchemy import desc, func, or_

from app.database import SessionLocal
from app.models import Code, Knowledge, LogEntry, LogFile
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

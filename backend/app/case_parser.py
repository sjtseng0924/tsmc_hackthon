import re
from typing import Iterable, Optional


SEVERITY_MAP = {
    "P0": "high",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
}


def _normalize_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned in {
            "事件時間軸:",
            "根本原因 (Root Cause):",
            "根本原因:",
            "解決方案 (Immediate Fix):",
            "之後如何避免 (Prevention Measures):",
        }:
            continue
        if cleaned.endswith(":") and len(cleaned) <= 12:
            continue
        lines.append(cleaned)
    return lines


def _extract_line_value(text: str, label: str) -> Optional[str]:
    pattern = rf"^{re.escape(label)}\s*[:：]\s*(.+)$"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _extract_section(text: str, start_pattern: str, end_patterns: Iterable[str]) -> str:
    start_match = re.search(start_pattern, text, flags=re.MULTILINE)
    if not start_match:
        return ""
    line_break = text.find("\n", start_match.end())
    if line_break == -1:
        return ""
    start_index = line_break + 1
    end_index = len(text)
    for pattern in end_patterns:
        end_match = re.search(pattern, text[start_index:], flags=re.MULTILINE)
        if end_match:
            end_index = min(end_index, start_index + end_match.start())
    return text[start_index:end_index].strip()


def _derive_severity(raw_value: Optional[str]) -> str:
    if not raw_value:
        return "medium"
    for key, mapped in SEVERITY_MAP.items():
        if key in raw_value.upper():
            return mapped
    if "HIGH" in raw_value.upper():
        return "high"
    if "LOW" in raw_value.upper():
        return "low"
    return "medium"


def _derive_tags(title: str, root_cause: str) -> list[str]:
    combined = f"{title} {root_cause}".lower()
    tags: list[str] = []
    if any(word in combined for word in ["login", "登入", "auth", "認證"]):
        tags.append("auth")
    if any(word in combined for word in ["database", "資料庫", "db", "連線池"]):
        tags.append("database")
    if any(word in combined for word in ["upload", "上傳", "s3", "storage"]):
        tags.append("storage")
    if any(word in combined for word in ["cache", "快取"]):
        tags.append("cache")
    if any(word in combined for word in ["timeout", "逾時", "延遲", "latency"]):
        tags.append("latency")
    if not tags:
        return []
    return sorted(set(tags))


def parse_case_text(text: str) -> dict:
    case_id = _extract_line_value(text, "文件編號") or "unknown"
    title = _extract_line_value(text, "事件標題") or "Untitled incident"
    severity_raw = _extract_line_value(text, "事件等級") or ""
    severity = _derive_severity(severity_raw)

    summary_section = _extract_section(
        text,
        r"^\s*2\.\s*報案問題.*$",
        [r"^\s*3\.\s*影響範圍", r"^\s*4\.\s*Issue 發生細節描述"],
    )
    summary_lines = _normalize_lines(summary_section)
    summary = summary_lines[0] if summary_lines else "No summary available."

    root_section = _extract_section(
        text,
        r"^.*根本原因.*$",
        [r"^.*事件時間軸.*$", r"^\s*5\.\s*解決方案"],
    )
    root_lines = _normalize_lines(root_section)
    root_cause = root_lines[0] if root_lines else "Unknown root cause."

    timeline_section = _extract_section(
        text,
        r"^.*事件時間軸.*$",
        [r"^\s*5\.\s*解決方案", r"^\s*6\.\s*之後如何避免"],
    )
    timeline = _normalize_lines(timeline_section)

    immediate_section = _extract_section(
        text,
        r"^\s*5\.\s*解決方案.*$",
        [r"^\s*6\.\s*之後如何避免"],
    )
    immediate_lines = _normalize_lines(immediate_section)
    immediate_fix = " ".join(immediate_lines) if immediate_lines else "No immediate fix recorded."

    long_term_section = _extract_section(text, r"^\s*6\.\s*之後如何避免.*$", [])
    long_term_lines = _normalize_lines(long_term_section)
    long_term_fix = " ".join(long_term_lines) if long_term_lines else "No long-term fix recorded."

    tags = _derive_tags(title, root_cause)

    return {
        "case_id": case_id,
        "title": title,
        "category": "Incident",
        "severity": severity,
        "summary": summary,
        "root_cause": root_cause,
        "timeline": timeline,
        "immediate_fix": immediate_fix,
        "long_term_fix": long_term_fix,
        "tags": tags,
        "references": [],
    }

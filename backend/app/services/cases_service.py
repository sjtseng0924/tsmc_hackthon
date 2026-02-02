from typing import Optional

from app.database import SessionLocal
from app.models import Knowledge


def _row_to_item(row: Knowledge) -> dict:
    return {
        "id": row.case_id,
        "title": row.title,
        "category": row.category,
        "severity": row.severity,
        "rootCause": row.root_cause,
        "tags": row.tags or [],
        "summary": row.summary,
        "timeline": row.timeline or [],
        "immediateFix": row.immediate_fix,
        "longTermFix": row.long_term_fix,
        "references": row.references or [],
    }


def list_case_items() -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Knowledge)
            .filter(Knowledge.root_cause.isnot(None))
            .order_by(Knowledge.case_id.asc())
            .all()
        )
        return [_row_to_item(row) for row in rows]
    finally:
        db.close()


def get_case_item(case_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        row = db.query(Knowledge).filter(Knowledge.case_id == case_id).first()
        return _row_to_item(row) if row else None
    finally:
        db.close()


def filter_case_items(
    items: list[dict],
    *,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    def matches(item: dict) -> bool:
        if category and item.get("category") != category:
            return False
        if severity and item.get("severity") != severity:
            return False
        if tag and tag not in (item.get("tags") or []):
            return False
        if search:
            haystack = " ".join(
                [
                    item.get("id", ""),
                    item.get("title", ""),
                    item.get("rootCause", ""),
                    item.get("category", ""),
                    " ".join(item.get("tags") or []),
                    item.get("summary", ""),
                ]
            ).lower()
            if search.lower() not in haystack:
                return False
        return True

    return [item for item in items if matches(item)]


def list_taxonomy(items: list[dict]) -> dict:
    categories = sorted({item.get("category") for item in items if item.get("category")})
    severities = sorted({item.get("severity") for item in items if item.get("severity")})
    tags: set[str] = set()
    for item in items:
        for value in item.get("tags") or []:
            tags.add(value)
    return {
        "categories": categories,
        "severities": severities,
        "tags": sorted(tags),
    }


def list_case_ids(items: list[dict]) -> list[str]:
    return [item.get("id", "") for item in items if item.get("id")]

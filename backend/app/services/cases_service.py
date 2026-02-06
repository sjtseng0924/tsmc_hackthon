from datetime import datetime
from typing import Optional, List, Dict, Any

from app.database import SessionLocal
from app.models import Knowledge
from app.services.case_parser import parse_case_text
from app.services.rag import get_embedding


def _row_to_item(row: Knowledge) -> dict:
    return {
        "filename": row.filename, # Was id
        "title": row.title,
        "severity": row.severity,
        "rootCause": row.root_cause,
        # "tags": row.tags or [], # Legacy removed
        "summary": row.report_problem, # Map report_problem to summary for compatibility
        "timeline": row.timeline or [],
        # "immediateFix": row.immediate_fix, # Legacy removed
        # "longTermFix": row.long_term_fix, # Legacy removed
        # "references": row.references or [], # Legacy removed
        
        # New Fields
        "reportDate": str(row.report_date) if row.report_date else None,
        "occurredAt": str(row.occurred_at) if row.occurred_at else None,
        "resolvedAt": str(row.resolved_at) if row.resolved_at else None,
        "reportProblem": row.report_problem,
        "impactService": row.impact_service,
        "impactUser": row.impact_user,
        "impactData": row.impact_data,
        "eventDetails": row.event_details,
        "inferenceProcess": row.inference_process,
        "solution": row.solution,
        "preventiveMeasures": row.preventive_measures or [],
        "hiddenRisks": row.hidden_risks,
    }


def list_case_items() -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Knowledge)
            .filter(Knowledge.root_cause.isnot(None))
            .order_by(Knowledge.filename.asc())
            .all()
        )
        return [_row_to_item(row) for row in rows]
    finally:
        db.close()


def get_case_item(filename: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        row = db.query(Knowledge).filter(Knowledge.filename == filename).first()
        return _row_to_item(row) if row else None
    finally:
        db.close()


def filter_case_items(
    items: list[dict],
    *,
    category: Optional[str] = None, # Legacy: might need removal or mapping
    severity: Optional[str] = None,
    tag: Optional[str] = None, # Legacy
    search: Optional[str] = None,
) -> list[dict]:
    def matches(item: dict) -> bool:
        # category removed from model
        if severity and item.get("severity") != severity:
            return False
        # tags removed from model
        if search:
            # Enhanced search
            haystack = " ".join(
                [
                    item.get("filename", ""),
                    item.get("title", ""),
                    item.get("rootCause", ""),
                    item.get("summary", ""), # Actually reportProblem
                    item.get("solution", ""),
                ]
            ).lower()
            if search.lower() not in haystack:
                return False
        return True

    return [item for item in items if matches(item)]


def list_taxonomy(items: list[dict]) -> dict:
    severities = sorted({item.get("severity") for item in items if item.get("severity")})
    return {
        "categories": [], # Legacy
        "severities": severities,
        "tags": [], # Legacy
    }


def list_case_ids(items: list[dict]) -> list[str]:
    return [item.get("filename", "") for item in items if item.get("filename")]


# 原始字串解析版本 (不再支援，因為 DB 結構已改)
def save_case_report(report_text: str, *, source: Optional[str] = None) -> Optional[str]:
    return None # Deprecated


# 新增：結構化資料儲存版本 (給 Agent Tool 使用)
def save_case_report_structured(data: Dict[str, Any]) -> Optional[str]:
    """
    Save strict structured data to DB.
    """
    # 組合一份 content text 作為 Embedding 用
    content_text = f"""
    Title: {data.get('title')}
    Severity: {data.get('severity')}
    Report Problem: {data.get('report_problem')}
    Root Cause: {data.get('root_cause')}
    Solution: {data.get('solution')}
    """
    return _save_to_db(data, content_text=content_text)


def _save_to_db(parsed: Dict[str, Any], content_text: str, source_ref: Optional[str] = None) -> Optional[str]:
    # Use filename as ID. If not provided, generate one.
    filename = parsed.get("filename")
    if not filename:
        # Auto generate INC-YYYYMMDD-HHMM.txt
        now_str = datetime.now().strftime('%Y%m%d-%H%M')
        filename = f"INC-{now_str}.txt"

    # Helper to parse datetime string if needed
    def parse_dt(dt_str):
        if not dt_str: return None
        if isinstance(dt_str, datetime): return dt_str
        
        # Basic cleanup: Remove everything after 'UTC'
        if "UTC" in dt_str:
            clean_str = dt_str.split("UTC")[0].strip()
        else:
            clean_str = dt_str.strip()
        
        try:
            return datetime.fromisoformat(clean_str)
        except:
            try:
                # Try format: YYYY-MM-DD HH:MM
                return datetime.strptime(clean_str, "%Y-%m-%d %H:%M")
            except:
                try:
                    # Try format: YYYY-MM-DD
                    return datetime.strptime(clean_str, "%Y-%m-%d")
                except:
                    return None

    db = SessionLocal()
    try:
        row = db.query(Knowledge).filter(Knowledge.filename == filename).first()
        vector = get_embedding(content_text)
        
        # New field values
        report_date = parse_dt(parsed.get("report_date"))
        occurred_at = parse_dt(parsed.get("occurred_at"))
        resolved_at = parse_dt(parsed.get("resolved_at"))
        
        if row:
            row.content = content_text
            row.vector = vector
            row.title = parsed.get("title")
            row.severity = parsed.get("severity")
            
            row.report_problem = parsed.get("report_problem")
            row.impact_service = parsed.get("impact_service")
            row.impact_user = parsed.get("impact_user")
            row.impact_data = parsed.get("impact_data")
            
            row.root_cause = parsed.get("root_cause")
            row.event_details = parsed.get("event_details")
            row.timeline = parsed.get("timeline")
            row.inference_process = parsed.get("inference_process")
            
            row.solution = parsed.get("solution")
            row.preventive_measures = parsed.get("preventive_measures")
            row.hidden_risks = parsed.get("hidden_risks")

        else:
            row = Knowledge(
                filename=filename,
                content=content_text,
                vector=vector,
                
                title=parsed.get("title"),
                severity=parsed.get("severity"),
                
                report_date=report_date,
                occurred_at=occurred_at,
                resolved_at=resolved_at,
                
                report_problem=parsed.get("report_problem"),
                impact_service=parsed.get("impact_service"),
                impact_user=parsed.get("impact_user"),
                impact_data=parsed.get("impact_data"),
                
                root_cause=parsed.get("root_cause"),
                event_details=parsed.get("event_details"),
                timeline=parsed.get("timeline"),
                inference_process=parsed.get("inference_process"),
                
                solution=parsed.get("solution"),
                preventive_measures=parsed.get("preventive_measures"),
                hidden_risks=parsed.get("hidden_risks"),
            )
            db.add(row)
        db.commit()
        return filename
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

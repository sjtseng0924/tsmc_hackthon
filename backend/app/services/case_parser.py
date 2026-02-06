import re
from typing import Optional, List, Dict, Any

def _extract_value(text: str, label: str) -> Optional[str]:
    """Extract value for a given label like 'Label: Value'"""
    # Pattern: Line starting with label, followed by colon, capturing the rest
    pattern = rf"^\s*{re.escape(label)}\s*[:：]\s*(.+)$"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None

def _extract_block(text: str, start_marker: str, end_markers: List[str]) -> str:
    """Extract text block between start_marker and any of the end_markers"""
    start_pos = text.find(start_marker)
    if start_pos == -1:
        return ""
    
    # Move start_pos to after the marker + newline
    content_start = text.find("\n", start_pos)
    if content_start == -1:
        return ""
    content_start += 1
    
    min_end_pos = len(text)
    for end_marker in end_markers:
        pos = text.find(end_marker, content_start)
        if pos != -1 and pos < min_end_pos:
            min_end_pos = pos
            
    return text[content_start:min_end_pos].strip()

def _parse_list_of_dicts(text: str, item_label: str) -> List[Dict[str, str]]:
    """
    Parse blocks like:
    預防措施 1: ...
    內容: ...
    負責人: ...
    參考連結: ...
    """
    items = []
    # Split by the item label (e.g. "預防措施")
    # This is a bit heuristic. We look for lines starting with "Label X:"
    pattern = rf"^\s*{re.escape(item_label)}\s*.*[:：]\s*(.+)$"
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    
    if not matches:
        return []

    for i, match in enumerate(matches):
        data = {}
        data["title"] = match.group(1).strip()
        
        # Determine extracting range for this item
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start_idx:end_idx]
        
        data["content"] = _extract_value(chunk, "內容") or ""
        data["owner"] = _extract_value(chunk, "負責人") or ""
        data["link"] = _extract_value(chunk, "參考連結") or ""
        
        # Specific handling for Hidden Risks which might not have "Responsible"
        # but the schema expects "content" and "link".
        
        items.append(data)
    return items

def parse_case_text(text: str) -> Dict[str, Any]:
    # 1. Basic Info
    filename = _extract_value(text, "文件編號")
    title = _extract_value(text, "事件標題")
    report_date = _extract_value(text, "報告日期")
    occurred_at = _extract_value(text, "Issue 發生時間")
    resolved_at = _extract_value(text, "Issue 解決時間")
    
    severity_raw = _extract_value(text, "事件等級")
    severity = "medium"
    if severity_raw:
        if "P0" in severity_raw: severity = "critical"
        elif "P1" in severity_raw: severity = "high"
        elif "P2" in severity_raw: severity = "medium"
        elif "P3" in severity_raw: severity = "low"

    # 2. Report Problem
    report_problem = _extract_block(text, "2. 報案問題", ["3. 影響範圍"])

    # 3. Impact
    impact_section = _extract_block(text, "3. 影響範圍", ["4. Issue 發生細節描述"])
    impact_service = _extract_block(impact_section, "服務影響", ["使用者影響", "資料影響"])
    impact_user = _extract_block(impact_section, "使用者影響", ["資料影響"])
    impact_data = _extract_block(impact_section, "資料影響", [])
    
    # 4. Details
    details_section = _extract_block(text, "4. Issue 發生細節描述", ["5. 解決方案"])
    root_cause = _extract_block(details_section, "根本原因", ["事件細節", "事件時間軸", "檔案閱讀推理過程"])
    event_details = _extract_block(details_section, "事件細節", ["事件時間軸", "檔案閱讀推理過程"])
    
    timeline_text = _extract_block(details_section, "事件時間軸", ["檔案閱讀推理過程"])
    timeline = [line.strip() for line in timeline_text.splitlines() if line.strip()]
    
    inference_process = _extract_block(details_section, "檔案閱讀推理過程", [])
    
    # 5. Solution
    solution = _extract_block(text, "5. 解決方案", ["6. 之後如何避免"])
    
    # 6. Future Prevention
    prevention_section = _extract_block(text, "6. 之後如何避免", [])
    
    # Split Prevention section into "Preventive Measures" and "Hidden Risks"
    # Assuming "未來預防措施" comes first, then "其他隱藏的危險及優化方法"
    
    risk_start = prevention_section.find("其他隱藏的危險及優化方法")
    if risk_start != -1:
        measures_text = prevention_section[:risk_start]
        risks_text = prevention_section[risk_start:]
    else:
        measures_text = prevention_section
        risks_text = ""
        
    preventive_measures = _parse_list_of_dicts(measures_text, "預防措施")
    # Using "標題" for hidden risks if user follows specific format, but usually it might be unstructured lists.
    # If the text uses "預防措施 X:" format, _parse_list_of_dicts works.
    # For Hidden Risks, user said: "請具體提出...". It might not be a list of "標題: ...".
    # But let's try to parse if there are clearly defined items, otherwise treat as text? 
    # The requirement says List of Dict. Let's try to parse "標題:" or generic bullets.
    # Actually prompt says: 
    #   - 標題 (Title)
    #   - 內容 (Content)
    #   - 參考連結 (Link)
    # So we can reuse similar parsing logic but look for "標題:" or maybe just parse bullets?
    # Let's adjust _parse_list_of_dicts to be more generic.
    
    # For now, let's assume the user format in Prompt (Title, Content, Link) matches roughly what we look for.
    # If the file text says "標題: xxx", we catch it.
    
    hidden_risks = []
    # Try to parse "標題:" pattern in risks_text
    risk_matches = list(re.finditer(r"^\s*標題\s*[:：]\s*(.+)$", risks_text, flags=re.MULTILINE))
    if risk_matches:
        for i, match in enumerate(risk_matches):
            data = {}
            data["title"] = match.group(1).strip()
            start_idx = match.end()
            end_idx = risk_matches[i+1].start() if i + 1 < len(risk_matches) else len(risks_text)
            chunk = risks_text[start_idx:end_idx]
            data["content"] = _extract_value(chunk, "內容") or chunk.strip() # Fallback to whole chunk if no "Content:"
            data["link"] = _extract_value(chunk, "參考連結") or ""
            hidden_risks.append(data)
    
    # If legacy "行動項目" (Action Item) is used in old files
    if not preventive_measures:
        preventive_measures = _parse_list_of_dicts(measures_text, "行動項目")

    return {
        "filename": filename,
        "title": title,
        "report_date": report_date,
        "occurred_at": occurred_at,
        "resolved_at": resolved_at,
        "severity": severity,
        
        "report_problem": report_problem,
        "impact_service": impact_service,
        "impact_user": impact_user,
        "impact_data": impact_data,
        
        "root_cause": root_cause,
        "event_details": event_details,
        "timeline": timeline,
        "inference_process": inference_process,
        
        "solution": solution,
        "preventive_measures": preventive_measures,
        "hidden_risks": hidden_risks
    }


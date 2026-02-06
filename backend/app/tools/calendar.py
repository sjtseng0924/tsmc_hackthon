import requests
import json
from typing import List, Optional
from app.config import settings

def _call_n8n(action: str, payload: dict) -> str:
    """Helper function to call the n8n webhook."""
    webhook_url = settings.N8N_CALENDAR_WEBHOOK_URL
    if not webhook_url:
        return "Error: N8N_CALENDAR_WEBHOOK_URL is not configured."

    try:
        print(f"DEBUG: Calling n8n webhook: {webhook_url}")
        print(f"DEBUG: Payload: action={action}, payload={payload}")
        
        response = requests.post(
            webhook_url,
            json={
                "action": action,
                "payload": payload
            },
            timeout=30  # n8n might take a moment to process
        )
        print(f"DEBUG: n8n Response Code: {response.status_code}")
        print(f"DEBUG: n8n Response Text: {response.text[:500]}") # Print first 500 chars

        response.raise_for_status()
        
        # Try to parse JSON response if possible, else return text
        try:
            data = response.json()
            
            # Helper to simplify event object
            def simplify_event(evt):
                if not isinstance(evt, dict):
                    return evt
                return {
                    "summary": evt.get("summary", "No Title"),
                    "start": evt.get("start"),
                    "end": evt.get("end"),
                    "location": evt.get("location"),
                    "description": evt.get("description", "")[:100] + "..." if evt.get("description") else None,
                    "attendees": [a.get("email") for a in evt.get("attendees", []) if isinstance(a, dict) and "email" in a],
                    "status": evt.get("status")
                }

            # Handle list_events response specifically
            if action == "list_events":
                items = []
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        items = data["data"]
                    elif "items" in data and isinstance(data["items"], list):
                        items = data["items"]
                elif isinstance(data, list):
                    items = data
                
                if items:
                    simplified_items = [simplify_event(i) for i in items]
                    return json.dumps(simplified_items, ensure_ascii=False)

            # If n8n returns a "text" or "message" field, use that
            if isinstance(data, dict):
                return data.get("text", data.get("message", json.dumps(data, ensure_ascii=False)))
            return json.dumps(data, ensure_ascii=False)
        except ValueError:
            return response.text

    except Exception as e:
        return f"Error calling n8n: {str(e)}"

def list_events(max_results: int = 10, calendar_id: str = "primary",  time_min: Optional[str] = None, time_max: Optional[str] = None):
    """
    Lists events. Can specify a time range.
    
    Args:
        max_results: The maximum number of events to return.
        calendar_id: The ID of the calendar (default: primary). To view a shared calendar, use the email address of the owner (e.g., 'colleague@example.com'). Ensure you have permission to view it.
        time_min: Start time in ISO format (e.g., '2023-10-27T00:00:00Z').
        time_max: End time in ISO format (e.g., '2023-10-27T23:59:59Z').
    """
    payload = {
        "maxResults": max_results,
        "calendarId": calendar_id,
        "timeMin": time_min,
        "timeMax": time_max
    }
        
    return _call_n8n("list_events", payload)


from sqlalchemy import text
from app.database import SessionLocal

def get_email_by_name(name: str) -> str:
    """
    Resolves a name to an email address using fuzzy matching.
    
    This function uses PostgreSQL's pg_trgm extension to find the most similar
    contact name, allowing for typos and small variations.
    
    Args:
        name: The person's name (can have typos)
        
    Returns:
        - The email address if a match is found (similarity >= 0.3)
        - The original input if it looks like an email (contains '@')
        - The original input if no match is found
        
    Examples:
        - "david" -> "david103132881@gmail.com"
        - "davd" (typo) -> "david103132881@gmail.com"
        - "kevin@example.com" -> "kevin@example.com" (pass-through)
    """
    name_stripped = name.strip()
    
    # If input looks like an email, return as-is
    if '@' in name_stripped:
        return name_stripped
    
    db = SessionLocal()
    try:
        # Use PostgreSQL trigram similarity for fuzzy matching
        # similarity() returns a score between 0 and 1
        # We order by similarity DESC and take the best match
        # Threshold of 0.2 works better for short names (3-5 chars)
        query = text("""
            SELECT email, name, similarity(LOWER(name), LOWER(:input_name)) as score
            FROM contacts
            WHERE is_active = 1
              AND similarity(LOWER(name), LOWER(:input_name)) > 0.2
            ORDER BY score DESC
            LIMIT 1
        """)
        
        result = db.execute(query, {"input_name": name_stripped}).fetchone()
        
        if result:
            email, matched_name, score = result
            print(f"DEBUG: Fuzzy matched '{name_stripped}' -> '{matched_name}' (email: {email}, score: {score:.2f})")
            return email
        else:
            print(f"DEBUG: No match found for '{name_stripped}', returning as-is")
            return name_stripped  # Return original if no match
            
    except Exception as e:
        print(f"ERROR: Failed to query contacts: {e}")
        return name_stripped  # Fallback to original input
    finally:
        db.close()



def check_availability(
    time_min: str, 
    time_max: str, 
    emails: List[str]
):
    """
    Check availability for a set of emails within a time range.
    Returns availability status and the next available free slot.
    
    This function ONLY checks availability. It does NOT create events or perform Discord actions.
    
    :param time_min: Start time in ISO format (e.g. 2024-01-01T09:00:00Z)
    :param time_max: End time in ISO format
    :param emails: List of email addresses to check
    """
    from app.services.n8n import n8n_client  # Delayed import
    
    # Only send the inner payload, n8n_client will wrap it with action
    payload = {
        "timeMin": time_min,
        "timeMax": time_max,
        "emails": emails
    }

    try:
        response = n8n_client.call_webhook("check_availability", payload)
        return response
    except Exception as e:
        return {"error": str(e)}


def find_available_slots(
    time_min: str, 
    time_max: str, 
    emails: List[str]
):
    """
    Find available slots (Alias for check_availability).
    """
    return check_availability(time_min, time_max, emails)


def create_event(
    start: str,
    end: str,
    summary: str,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None
):
    """
    Create a Google Calendar event.
    
    :param start: Start time in ISO format
    :param end: End time in ISO format
    :param summary: Event title
    :param description: Event description
    :param attendees: List of attendee emails
    """
    from app.services.n8n import n8n_client

    payload = {
        "start": start,
        "end": end,
        "summary": summary,
        "description": description,
        "attendees": attendees or []
    }

    try:
        response = n8n_client.call_webhook("create_event", payload)
        return response
    except Exception as e:
        return {"error": str(e)}
    


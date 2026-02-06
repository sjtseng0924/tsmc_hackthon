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


# Mock Contact List - In production, this would come from a DB or LDAP
CONTACT_LIST = {
    "ivan": "ivan@example.com",
    "kevin": "kevin@example.com",
    "david": "david103132881@gmail.com", 
    "cindy": "cindy@example.com",
    "alice": "alice@example.com",
    "bob": "bob@example.com"
}

def get_email_by_name(name: str) -> str:
    """Resolves a name to an email address."""
    name_lower = name.lower().strip()
    return CONTACT_LIST.get(name_lower, name)  # Return original if not found (assume it's an email)


def check_availability(
    time_min: str, 
    time_max: str, 
    emails: List[str]
):
    """
    Checks the free/busy status for a list of email addresses.
    
    Args:
        time_min: Start time in ISO format (e.g., '2023-10-27T09:00:00Z').
        time_max: End time in ISO format (e.g., '2023-10-27T17:00:00Z').
        emails: A list of email addresses OR names (e.g. ["Ivan", "kevin@example.com"]).
    """
    resolved_emails = [get_email_by_name(e) for e in emails]
    
    return _call_n8n("check_availability", {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": resolved_emails
    })

def create_event(
    summary: str, 
    start_time: str, 
    end_time: str, 
    attendees: List[str] = [],
    calendar_id: str = "primary",
    is_allday: bool = False
):
    """
    Creates a new event and invites attendees.
    
    Args:
        summary: The title of the event.
        start_time: Start time in ISO format (e.g. '2023-10-27T09:00:00') or date format ('2023-10-27') for all-day.
        end_time: End time in ISO format or date format.
        attendees: List of email addresses to invite.
        calendar_id: The ID of the calendar to create event in.
        is_allday: Set to True if this is an all-day event.
    """
    
    # Construct the base event dictionary
    resolved_attendees = [get_email_by_name(a) for a in attendees]
    event_payload = {
        "calendarId": calendar_id,
        "summary": summary,
        "attendees": [{"email": email} for email in resolved_attendees]
    }
    
    if is_allday:
        # For all-day events, use 'date'. ensure we only send YYYY-MM-DD
        # Even if the agent sends ISO with time, we strip it.
        start_date = start_time.split('T')[0]
        end_date = end_time.split('T')[0]
        
        event_payload["start"] = {"date": start_date}
        event_payload["end"] = {"date": end_date}
    else:
        # Regular events use 'dateTime'
        event_payload["start"] = {"dateTime": start_time}
        event_payload["end"] = {"dateTime": end_time}

    return _call_n8n("create_event", event_payload)

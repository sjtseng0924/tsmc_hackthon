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
        calendar_id: The ID of the calendar (default: primary).
        time_min: Start time in ISO format (e.g., '2023-10-27T00:00:00Z').
        time_max: End time in ISO format (e.g., '2023-10-27T23:59:59Z').
    """
    payload = {
        "maxResults": max_results,
        "calendarId": calendar_id
    }
    if time_min:
        payload["timeMin"] = time_min
    if time_max:
        payload["timeMax"] = time_max
        
    return _call_n8n("list_events", payload)

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
        emails: A list of email addresses to check.
    """
    return _call_n8n("check_availability", {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": email} for email in emails]
    })

def create_event(
    summary: str, 
    start_time: str, 
    end_time: str, 
    attendees: List[str] = [],
    calendar_id: str = "primary"
):
    """
    Creates a new event and invites attendees.
    
    Args:
        summary: The title of the event.
        start_time: Start time in ISO format.
        end_time: End time in ISO format.
        attendees: List of email addresses to invite.
        calendar_id: The ID of the calendar to create event in.
    """
    return _call_n8n("create_event", {
        "calendarId": calendar_id,
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
        "attendees": [{"email": email} for email in attendees]
    })

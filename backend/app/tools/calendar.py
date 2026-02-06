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
    emails: List[str],
    add_to_channel: bool = False,
    channel_id: Optional[str] = None,
    discord_user_name: Optional[str] = None,
    create_event: bool = False,
    event_summary: Optional[str] = None,
    event_description: Optional[str] = None
):
    """
    Checks availability and optionally performs actions if the person is free.
    
    This tool creates a seamless flow:
    1. Check if the person is available
    2. IF AVAILABLE:
       - Can automatically add them to a Discord channel (set add_to_channel=True)
       - Can automatically create a calendar event (set create_event=True)
    3. Returns availability status + result of actions taken
    
    Args:
        time_min: Start time in ISO format
        time_max: End time in ISO format
        emails: List of emails or names
        add_to_channel: If True, add to Discord channel when available
        channel_id: Discord Channel ID as a STRING (required if add_to_channel is True)
        discord_user_name: Name to find Discord ID (defaults to name from emails)
        create_event: If True, create calendar event when available
        event_summary: Title of event (required if create_event is True)
        event_description: Description of event
    """
    resolved_emails = [get_email_by_name(e) for e in emails]
    
    # Basic payload
    payload = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": resolved_emails
    }
    
    # Add conditional actions to payload
    if add_to_channel:
        payload["add_to_channel"] = True
        if channel_id:
            payload["channel_id"] = str(channel_id)  # Convert to string to prevent loss of precision in JS/n8n
        
        # Resolve Discord ID locally
        target_name = None
        if discord_user_name:
            target_name = discord_user_name
        elif emails:
            # Simple heuristic: use the first person's name derived from email if not provided
            target_name = emails[0].split('@')[0]
            
        if target_name:
            payload["name"] = target_name
            # Try to resolve ID
            from app.tools.discord import get_discord_id_by_name
            resolved_discord_id = get_discord_id_by_name(target_name)
            if resolved_discord_id:
                payload["discord_id"] = resolved_discord_id
                print(f"DEBUG: Resolved discord_id {resolved_discord_id} for {target_name}")
            else:
                print(f"DEBUG: Could not resolve discord_id for {target_name}")

    if create_event:
        payload["create_event"] = True
        payload["event_details"] = {
            "summary": event_summary or "Meeting",
            "description": event_description or "",
            "start": {"dateTime": time_min},
            "end": {"dateTime": time_max},
            "attendees": [{"email": e} for e in resolved_emails]
        }
    
    
    return _call_n8n("check_availability", payload)

def find_available_slots(
    time_min: str, 
    time_max: str, 
    emails: List[str],
    add_to_channel: bool = False,
    channel_id: Optional[str] = None,
    discord_user_name: Optional[str] = None,
    create_event: bool = False,
    event_summary: Optional[str] = None,
    event_description: Optional[str] = None
):
    """
    Alias for check_availability - finds when a person is available.
    
    This is identical to check_availability and exists for backward compatibility.
    It returns BOTH current availability status AND next free slot within 2 days.
    
    Args:
        time_min: Start availability search range
        time_max: End availability search range
        emails: A list of email addresses OR names
        add_to_channel: If True, add to Discord channel when available
        channel_id: Discord Channel ID as a STRING (required if add_to_channel is True)
        discord_user_name: Name to find Discord ID (defaults to name from emails)
        create_event: If True, create calendar event when available
        event_summary: Title of event (required if create_event is True)
        event_description: Description of event
    """
    # Just call check_availability - they now do the same thing
    return check_availability(
        time_min, 
        time_max, 
        emails, 
        add_to_channel, 
        channel_id, 
        discord_user_name, 
        create_event, 
        event_summary, 
        event_description
    )

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

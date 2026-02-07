import requests
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class N8NClient:
    def __init__(self):
        pass

    @property
    def webhook_url(self):
        return settings.N8N_CALENDAR_WEBHOOK_URL

    def call_webhook(self, action: str, payload: dict) -> dict:
        url = self.webhook_url
        if not url:
            raise ValueError("N8N_CALENDAR_WEBHOOK_URL is not configured.")

        logger.info(f"Calling n8n webhook: action={action}")
        print(f"DEBUG: Calling n8n webhook: {url} action={action}") # Print for Docker logs
        
        try:
            response = requests.post(
                url,
                json={
                    "action": action,
                    "payload": payload
                },
                timeout=30
            )
            
            # Log response for debugging
            print(f"DEBUG: n8n Response Status: {response.status_code}")
            print(f"DEBUG: n8n Response Body: {response.text[:200]}")

            response.raise_for_status()
            
            try:
                data = response.json()
                if isinstance(data, dict):
                    return data
                return {"result": data}
            except ValueError:
                return {"text": response.text}

        except Exception as e:
            logger.error(f"Failed to call n8n: {e}")
            print(f"ERROR: Failed to call n8n: {e}")
            raise e

n8n_client = N8NClient()

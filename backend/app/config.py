from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    BACKEND_ROOT: str = str(Path(__file__).resolve().parents[1])
    DISCORD_TOKEN: Optional[str] = None
    DISCORD_WEBHOOK_URL_1: Optional[str] = None
    DISCORD_WEBHOOK_URL_2: Optional[str] = None
    DISCORD_WEBHOOK_URL_3: Optional[str] = None
    DISCORD_BOT_ID: Optional[int] = None
    DISCORD_BOT_NAME: Optional[str] = None
    DISCORD_CHANNEL_ID_1: Optional[int] = None
    DISCORD_CHANNEL_ID_2: Optional[int] = None
    DISCORD_CHANNEL_ID_3: Optional[int] = None
    PORT: int = 8000
    
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_CX: Optional[str] = None
    VERTEX_PROJECT: Optional[str] = None
    VERTEX_LOCATION: Optional[str] = "us-central1"
    
    # n8n Integration
    N8N_CALENDAR_WEBHOOK_URL: Optional[str] = None
    VERTEX_EMBEDDING_LOCATION: Optional[str] = "us-central1"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    VERTEX_AGENT_LOCATION: Optional[str] = "us-central1"
    AGENT_MODEL: str = "gemini-2.5-pro"
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

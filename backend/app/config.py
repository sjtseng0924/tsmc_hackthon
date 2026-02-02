from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    BACKEND_ROOT: str = str(Path(__file__).resolve().parents[1])
    DISCORD_TOKEN: Optional[str] = None
    DISCORD_WEBHOOK_URL: Optional[str] = None
    DISCORD_BOT_ID: Optional[int] = None
    DISCORD_BOT_NAME: Optional[str] = None
    PORT: int = 8000
    
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    VERTEX_PROJECT: Optional[str] = None
    VERTEX_LOCATION: Optional[str] = "us-central1"
    VERTEX_EMBEDDING_LOCATION: Optional[str] = "us-central1"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

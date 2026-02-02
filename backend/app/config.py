from pathlib import Path

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    BACKEND_ROOT: str = str(Path(__file__).resolve().parents[1])
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

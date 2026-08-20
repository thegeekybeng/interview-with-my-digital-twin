import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://100.64.0.1:11434")
    PG_DSN: str = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/your_pgdb_name")
    TRACKER_DB: str = os.getenv("TRACKER_DB", "abuse_tracker.db")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

settings = Settings()

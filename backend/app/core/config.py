import os

class Settings:
    def __init__(self):
        self.OLLAMA_URL: str = os.getenv("OLLAMA_URL") or "http://localhost:11434"
        self.PG_DSN: str = os.getenv("PG_DSN") or "postgresql://postgres:postgres@localhost:5432/your_pgdb_name"
        self.TRACKER_DB: str = os.getenv("TRACKER_DB") or "abuse_tracker.db"
        self.SMTP_HOST: str = os.getenv("SMTP_HOST") or "smtp.gmail.com"
        
        port_val = os.getenv("SMTP_PORT")
        self.SMTP_PORT: int = int(port_val) if port_val and port_val.isdigit() else 587
        
        self.SMTP_USER: str = os.getenv("SMTP_USER") or ""
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD") or ""

settings = Settings()

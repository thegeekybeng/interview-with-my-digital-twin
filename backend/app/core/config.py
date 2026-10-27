import os

class Settings:
    def __init__(self):
        self.OLLAMA_URL: str = os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_HOST") or "http://localhost:11434"
        self.OLLAMA_HOST: str = self.OLLAMA_URL
        self.PG_DSN: str = os.getenv("PG_DSN") or "postgresql://postgres:postgres@localhost:5432/twin_db"
        self.TRACKER_DB: str = os.getenv("TRACKER_DB") or "abuse_tracker.db"
        self.PROJECT_NAME: str = "Andrew Yeo Digital Twin"
        self.VERSION: str = "2.0.0"
        self.MAX_STRIKES: int = 3
        self.MAX_INPUT_LENGTH: int = 1000
        self.OTP_EXPIRY_MINUTES: int = 10
        
        self.SMTP_HOST: str = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER") or "smtp.gmail.com"
        self.SMTP_SERVER: str = self.SMTP_HOST
        
        port_val = os.getenv("SMTP_PORT")
        self.SMTP_PORT: int = int(port_val) if port_val and port_val.isdigit() else 587
        
        self.SMTP_USER: str = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or ""
        self.SMTP_USERNAME: str = self.SMTP_USER
        self.SENDER_EMAIL: str = self.SMTP_USER
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD") or ""

settings = Settings()

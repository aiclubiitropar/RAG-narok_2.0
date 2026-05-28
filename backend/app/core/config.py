import os
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAGnarok 2.0"
    VERSION: str = "2.0.0"
    
    # Qdrant configurations
    QDRANT_URL: str = os.getenv("QDRANT_URL", "https://c44fd71d-99f2-4329-b661-b069e0598086.us-east-2-0.aws.cloud.qdrant.io:6333")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
    QDRANT_LONGTERM_COLLECTION: str = "longterm_db"
    QDRANT_SHORTTERM_COLLECTION: str = "shortterm_db"
    
    # Redis & Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Hugging Face
    HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")
    HF_REPO_ID: str = "iotacluster/rag-narok-backend"

    # Emergency Settings
    EMERGENCY_KILL_COMMAND: Optional[str] = os.getenv("EMERGENCY_KILL_COMMAND")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "123456789")
    APPS_SCRIPT_WEBHOOK_URL: Optional[str] = os.getenv("APPS_SCRIPT_WEBHOOK_URL", "https://script.google.com/macros/s/AKfycbx5Kfcsg6g7ridcIkcbcON3YXWwZb3j6CT70JMNumntS7S9MbSRYH4gENWqtXhWc5zD/exec")

    # LLM (Groq) configurations
    GROQ_API_KEYS: str = os.getenv("GROQ_API_KEYS", "") # comma separated list of keys
    
    # Supabase (optional here, mostly frontend uses it, but backend might verify JWTs)
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = os.getenv("SUPABASE_KEY")
    SUPABASE_JWT_SECRET: Optional[str] = os.getenv("SUPABASE_JWT_SECRET")

    # Mem0
    MEM0_API_KEY: Optional[str] = os.getenv("MEM0_API_KEY")

    # SMTP/Email settings
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_SERVICE_URL: Optional[str] = os.getenv("EMAIL_SERVICE_URL")
    EMAIL_SERVICE_API_KEY: Optional[str] = os.getenv("EMAIL_SERVICE_API_KEY")

    class Config:
        env_file = "../.env"
        extra = "ignore"

settings = Settings()

if settings.HF_TOKEN:
    os.environ["HF_TOKEN"] = settings.HF_TOKEN

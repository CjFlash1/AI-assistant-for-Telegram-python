import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ADMIN_ID: int

    # AI
    OPENROUTER_API_KEY: str
    GOOGLE_API_KEY: str

    # Pinecone
    PINECONE_API_KEY: str
    PINECONE_ENV: str = "gcp-starter"
    PINECONE_INDEX_NAME: str = "telegram-memory"
    PINECONE_NAMESPACE: str = "default"

    # App
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings()

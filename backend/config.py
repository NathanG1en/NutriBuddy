# backend/config.py
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    openai_api_key: str = ""
    USDA_KEY: str = "DEMO_KEY"

    # Optional: LangSmith tracing
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "food_label_agent"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env vars


settings = Settings()
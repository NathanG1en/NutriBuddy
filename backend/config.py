# backend/config.py
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

from pydantic import Field


class Settings(BaseSettings):
    openai_api_key: str = ""
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    USDA_KEY: str = "DEMO_KEY"

    # Optional: LangSmith tracing
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "food_label_agent"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env vars


settings = Settings()

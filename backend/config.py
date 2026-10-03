from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    USDA_KEY: str = "DEMO_KEY"

    # Optional: LangSmith tracing
    langchain_api_key: Optional[str] = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "food_label_agent"


settings = Settings()

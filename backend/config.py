# backend/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    USDA_KEY: str = "DEMO_KEY"

    class Config:
        env_file = ".env"


settings = Settings()
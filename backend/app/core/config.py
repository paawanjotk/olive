import os
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Yuno Chat"
    DESCRIPTION: str = "Yuno Chat API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://ollivechat.netlify.app"
    ]

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ollive_chat"

    # LLM provider credentials
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Anthropic model config
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 8096
    OBSERVE_ME_ENDPOINT: str = os.getenv("OBSERVE_ME_ENDPOINT", "")

    # Gemini model config
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_TOKENS: int = 8096

    # OpenAI model config
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 8096

    class Config:
        env_file = ".env"


settings = Settings()

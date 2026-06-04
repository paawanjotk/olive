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
        "https://yuno-ayaan.netlify.app"
    ]

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5433/ollive_chat"

    # Redis — Celery broker/result backend + workflow event pub/sub
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Telegram bot (messaging channel)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

    # Slack messaging channel
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_APP_TOKEN: str = os.getenv("SLACK_APP_TOKEN", "")

    # MCP OAuth integrations
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    NOTION_CLIENT_ID: str = os.getenv("NOTION_CLIENT_ID", "")
    NOTION_CLIENT_SECRET: str = os.getenv("NOTION_CLIENT_SECRET", "")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Supabase auth
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

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

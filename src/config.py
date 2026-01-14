#neural-inbox1/config.py
"""
Configuration settings for Neural Inbox.
Supports Railway deployment with PostgreSQL.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration."""
    host: str
    port: int
    user: str
    password: str
    database: str
    ssl: bool = False

    @property
    def url(self) -> str:
        """SQLAlchemy async database URL."""
        base = f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        if self.ssl:
            return f"{base}?ssl=require"
        return base

    @property
    def sync_url(self) -> str:
        """SQLAlchemy sync database URL (for migrations)."""
        base = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        if self.ssl:
            return f"{base}?sslmode=require"
        return base


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    webapp_url: Optional[str] = None


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"


@dataclass
class Config:
    """Main application configuration."""
    database: DatabaseConfig
    telegram: TelegramConfig
    openai: OpenAIConfig

    debug: bool = False
    timezone: str = "Asia/Almaty"
    default_language: str = "ru"


def load_config() -> Config:
    """Load configuration from environment variables."""
    database_url = os.getenv("DATABASE_URL", "")

    if database_url:
        # Parse DATABASE_URL (Railway, Neon, Supabase, etc.)
        url = database_url.replace("postgresql://", "")
        user_pass, host_db = url.split("@")
        user, password = user_pass.split(":")
        host_port, database = host_db.split("/")

        # Handle SSL parameters in query string
        ssl = False
        if "?" in database:
            database, query = database.split("?", 1)
            ssl = "sslmode=require" in query or "ssl=require" in query

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 5432

        db_config = DatabaseConfig(
            host=host, port=port, user=user,
            password=password, database=database, ssl=ssl
        )
    else:
        db_config = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            database=os.getenv("DB_NAME", "neural_inbox")
        )

    telegram_config = TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        webapp_url=os.getenv("WEBAPP_URL")
    )

    openai_config = OpenAIConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    return Config(
        database=db_config,
        telegram=telegram_config,
        openai=openai_config,
        debug=os.getenv("DEBUG", "false").lower() == "true",
        timezone=os.getenv("TIMEZONE", "Asia/Almaty"),
        default_language=os.getenv("DEFAULT_LANGUAGE", "ru")
    )


config = load_config()

# Input limits
MAX_VOICE_DURATION: int = 300  # 5 минут
MAX_FILE_SIZE: int = 25 * 1024 * 1024  # 25MB
MAX_IMAGE_SIZE: int = 20 * 1024 * 1024  # 20MB
MAX_DOCUMENT_PAGES: int = 50
OCR_MAX_PAGES: int = 4
URL_FETCH_TIMEOUT: int = 10

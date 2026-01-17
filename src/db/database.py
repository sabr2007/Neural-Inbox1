# neural-inbox1/src/db/database.py
"""Database connection and session management."""
import ssl
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.config import config
from src.db.models import Base


# Create SSL context for Neon/cloud PostgreSQL providers
def _get_connect_args() -> dict:
    """Get connection arguments based on SSL requirements."""
    if config.database.ssl:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return {"ssl": ssl_context}
    return {}


engine = create_async_engine(
    config.database.url,
    echo=config.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_get_connect_args()
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db() -> None:
    """Initialize database - create tables if they don't exist."""
    async with engine.begin() as conn:
        # Enable pgvector extension for vector embeddings
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        # Update valid_status constraint to include 'processing'
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'valid_status') THEN
                    ALTER TABLE items DROP CONSTRAINT valid_status;
                END IF;
                ALTER TABLE items ADD CONSTRAINT valid_status
                    CHECK (status IN ('processing', 'inbox', 'active', 'done', 'archived'));
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
        """))

        # Add attachment_filename column if it doesn't exist
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'items' AND column_name = 'attachment_filename'
                ) THEN
                    ALTER TABLE items ADD COLUMN attachment_filename VARCHAR(255);
                END IF;
            END $$;
        """))


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes."""
    async with get_session() as session:
        yield session

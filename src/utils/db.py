"""PostgreSQL connection pool management using asyncpg."""

import os
import logging
import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


def _get_dsn() -> str:
    """Build PostgreSQL DSN from environment variables."""
    # Check for full DATABASE_URL first (Railway provides this)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Railway uses postgres:// but asyncpg needs postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "admin")
    password = os.getenv("POSTGRES_PASSWORD", "eproc_dev_2026")
    db = os.getenv("POSTGRES_DB", "eproc_rag")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def init_pool(min_size: int = 2, max_size: int = 10) -> None:
    """Initialize the global connection pool."""
    global _pool
    if _pool is not None:
        return

    dsn = _get_dsn()
    logger.info(f"Connecting to PostgreSQL at {dsn.split('@')[-1]}")

    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
    )
    logger.info("PostgreSQL connection pool initialized")


async def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


async def get_db_connection() -> asyncpg.Connection:
    """Acquire a connection from the pool."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return await _pool.acquire()


async def release_db_connection(conn: asyncpg.Connection) -> None:
    """Release a connection back to the pool."""
    if _pool is not None:
        await _pool.release(conn)

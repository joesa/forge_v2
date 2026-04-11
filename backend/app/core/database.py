from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine_write = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

engine_read = create_async_engine(
    settings.effective_read_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

_write_session_factory = async_sessionmaker(engine_write, expire_on_commit=False)
_read_session_factory = async_sessionmaker(engine_read, expire_on_commit=False)


@asynccontextmanager
async def get_write_session() -> AsyncGenerator[AsyncSession]:
    async with _write_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_read_session() -> AsyncGenerator[AsyncSession]:
    async with _read_session_factory() as session:
        yield session

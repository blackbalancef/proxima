from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from proxima.logging import get_logger
from proxima.settings import Settings

logger = get_logger(__name__)


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.async_database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self._session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        logger.info("database_engine_created", pool_size=10, max_overflow=20)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
        logger.info("database_closed")

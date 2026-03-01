from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select, update

from proxima.db.engine import Database
from proxima.db.models import MCPConfig


class MCPConfigRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def find_by_project(self, project_id: int) -> list[MCPConfig]:
        async with self.db.session() as session:
            result = await session.execute(
                select(MCPConfig)
                .where(MCPConfig.project_id == project_id)
                .order_by(MCPConfig.server_name)
            )
            return list(result.scalars().all())

    async def find_enabled_by_project(self, project_id: int) -> list[MCPConfig]:
        async with self.db.session() as session:
            result = await session.execute(
                select(MCPConfig)
                .where(MCPConfig.project_id == project_id)
                .where(MCPConfig.enabled.is_(True))
            )
            return list(result.scalars().all())

    async def upsert(self, values: Mapping[str, Any]) -> MCPConfig:
        async with self.db.session() as session:
            result = await session.execute(
                select(MCPConfig)
                .where(MCPConfig.project_id == int(values["project_id"]))
                .where(MCPConfig.server_name == str(values["server_name"]))
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.config_json = str(values["config_json"])
                existing.enabled = bool(values.get("enabled", True))
                await session.commit()
                await session.refresh(existing)
                return existing

            config = MCPConfig(**dict(values))
            session.add(config)
            await session.commit()
            await session.refresh(config)
            return config

    async def toggle(self, mcp_id: int, enabled: bool) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(MCPConfig).where(MCPConfig.id == mcp_id).values(enabled=enabled)
            )
            await session.commit()

    async def delete_by_id(self, mcp_id: int) -> None:
        async with self.db.session() as session:
            config = await session.get(MCPConfig, mcp_id)
            if config is None:
                return
            await session.delete(config)
            await session.commit()

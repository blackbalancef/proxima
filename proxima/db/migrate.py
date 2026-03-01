from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def run_migrations(engine: AsyncEngine) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS projects (
          id SERIAL PRIMARY KEY,
          telegram_chat_id BIGINT NOT NULL,
          name TEXT NOT NULL,
          directory TEXT NOT NULL,
          is_active BOOLEAN NOT NULL DEFAULT false,
          permission_mode TEXT NOT NULL DEFAULT 'default',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(telegram_chat_id, name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
          id SERIAL PRIMARY KEY,
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          claude_session_id TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          last_activity TIMESTAMPTZ NOT NULL DEFAULT now(),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mcp_configs (
          id SERIAL PRIMARY KEY,
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          server_name TEXT NOT NULL,
          config_json TEXT NOT NULL DEFAULT '{}',
          enabled BOOLEAN NOT NULL DEFAULT true,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(project_id, server_name)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_projects_chat_active
        ON projects(telegram_chat_id, is_active)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_project
        ON sessions(project_id)
        """,
        """
        ALTER TABLE sessions ADD COLUMN IF NOT EXISTS message_thread_id BIGINT
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sessions_thread
        ON sessions(message_thread_id)
        """,
        """
        ALTER TABLE sessions ADD COLUMN IF NOT EXISTS model TEXT
        """,
    ]

    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from proxima.claude.session_manager import SessionManager

if TYPE_CHECKING:
    from proxima.claude.limit_keeper import LimitKeeper
from proxima.commands.storage import CommandStorage
from proxima.db.engine import Database
from proxima.db.repositories.mcp_config import MCPConfigRepository
from proxima.db.repositories.project import ProjectRepository
from proxima.db.repositories.session import SessionRepository
from proxima.settings import Settings


@dataclass
class Services:
    settings: Settings
    db: Database
    projects: ProjectRepository
    sessions: SessionRepository
    mcp_configs: MCPConfigRepository
    session_manager: SessionManager
    command_storage: CommandStorage
    limit_keeper: LimitKeeper | None = field(default=None)
    claude_slash_commands: set[str] = field(default_factory=set)


def build_services(settings: Settings) -> Services:
    db = Database(settings)
    sessions = SessionRepository(db)
    return Services(
        settings=settings,
        db=db,
        projects=ProjectRepository(db),
        sessions=sessions,
        mcp_configs=MCPConfigRepository(db),
        session_manager=SessionManager(sessions),
        command_storage=CommandStorage(),
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandInfo:
    name: str
    scope: str  # "user" | "project"
    description: str  # first line of .md
    path: Path


class CommandStorage:
    def __init__(self, global_dir: Path | None = None) -> None:
        self._global_dir = global_dir or Path.home() / ".claude" / "commands"

    def _project_dir(self, project_dir: str) -> Path:
        return Path(project_dir) / ".claude" / "commands"

    def _resolve_path(self, name: str, scope: str, project_dir: str) -> Path:
        if scope == "user":
            return self._global_dir / f"{name}.md"
        return self._project_dir(project_dir) / f"{name}.md"

    def list_all(self, project_dir: str) -> list[CommandInfo]:
        commands: list[CommandInfo] = []
        dirs = [("user", self._global_dir), ("project", self._project_dir(project_dir))]
        for scope, directory in dirs:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.md")):
                first_line = path.read_text(encoding="utf-8").split("\n", maxsplit=1)[0].strip()
                commands.append(
                    CommandInfo(
                        name=path.stem,
                        scope=scope,
                        description=first_line,
                        path=path,
                    )
                )
        return commands

    def get(self, name: str, scope: str, project_dir: str) -> str | None:
        path = self._resolve_path(name, scope, project_dir)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save(self, name: str, scope: str, project_dir: str, content: str) -> Path:
        path = self._resolve_path(name, scope, project_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def delete(self, name: str, scope: str, project_dir: str) -> bool:
        path = self._resolve_path(name, scope, project_dir)
        if not path.exists():
            return False
        path.unlink()
        return True

    def resolve_prompt(self, name: str, scope: str, project_dir: str, arguments: str) -> str | None:
        content = self.get(name, scope, project_dir)
        if content is None:
            return None
        return content.replace("$ARGUMENTS", arguments)

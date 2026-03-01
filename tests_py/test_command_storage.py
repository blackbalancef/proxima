from __future__ import annotations

from pathlib import Path

from proxima.commands.storage import CommandStorage


def test_save_and_get(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    project_dir = tmp_path / "project"
    storage = CommandStorage(global_dir=global_dir)

    path = storage.save("greet", "user", str(project_dir), "Hello $ARGUMENTS!")
    assert path.exists()
    assert path.parent == global_dir

    content = storage.get("greet", "user", str(project_dir))
    assert content == "Hello $ARGUMENTS!"


def test_save_project_scope(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    project_dir = tmp_path / "project"
    storage = CommandStorage(global_dir=global_dir)

    path = storage.save("build", "project", str(project_dir), "Run build for $ARGUMENTS")
    assert path.exists()
    assert ".claude/commands" in str(path)
    assert path.parent == project_dir / ".claude" / "commands"


def test_list_all(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    project_dir = tmp_path / "project"
    storage = CommandStorage(global_dir=global_dir)

    storage.save("alpha", "user", str(project_dir), "Alpha command")
    storage.save("beta", "project", str(project_dir), "Beta command")

    commands = storage.list_all(str(project_dir))
    assert len(commands) == 2
    names = {c.name for c in commands}
    assert names == {"alpha", "beta"}
    scopes = {c.name: c.scope for c in commands}
    assert scopes["alpha"] == "user"
    assert scopes["beta"] == "project"


def test_delete(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    project_dir = tmp_path / "project"
    storage = CommandStorage(global_dir=global_dir)

    storage.save("temp", "user", str(project_dir), "Temp")
    assert storage.delete("temp", "user", str(project_dir)) is True
    assert storage.get("temp", "user", str(project_dir)) is None
    assert storage.delete("temp", "user", str(project_dir)) is False


def test_resolve_prompt_with_arguments(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    project_dir = tmp_path / "project"
    storage = CommandStorage(global_dir=global_dir)

    storage.save("deploy", "user", str(project_dir), "Deploy $ARGUMENTS to production")
    result = storage.resolve_prompt("deploy", "user", str(project_dir), "v1.2.3")
    assert result == "Deploy v1.2.3 to production"


def test_resolve_prompt_not_found(tmp_path: Path) -> None:
    storage = CommandStorage(global_dir=tmp_path / "global")
    result = storage.resolve_prompt("missing", "user", str(tmp_path / "project"), "args")
    assert result is None


def test_description_is_first_line(tmp_path: Path) -> None:
    global_dir = tmp_path / "global"
    project_dir = tmp_path / "project"
    storage = CommandStorage(global_dir=global_dir)

    storage.save("multi", "user", str(project_dir), "First line description\nSecond line content")
    commands = storage.list_all(str(project_dir))
    assert len(commands) == 1
    assert commands[0].description == "First line description"

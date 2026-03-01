from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil
import typer
from rich.console import Console

from proxima.cli.setup import main_cli as run_setup_wizard

PID_DIR = Path(".proxima")
PID_FILE = PID_DIR / "bot.pid"
LOG_FILE = PID_DIR / "bot.log"


def _python_cmd() -> list[str]:
    """Return command prefix to run Python with uv if available."""
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "python"]
    return [sys.executable]

console = Console()
app = typer.Typer(
    name="proxima",
    help="Proxima — Telegram bot for Claude Code.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _ensure_db() -> None:
    """Start PostgreSQL via docker compose if available."""
    try:
        result = subprocess.run(  # noqa: S603
            ["docker", "compose", "up", "-d", "db"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("[green]DB started.[/green]")
        else:
            console.print(f"[yellow]docker compose up -d db:[/yellow] {result.stderr.strip()}")
    except FileNotFoundError:
        console.print("[dim]Docker not found, skipping DB start.[/dim]")


def _build_env(verbose: bool) -> dict[str, str]:
    env = os.environ.copy()
    if verbose:
        env["LOG_LEVEL"] = "debug"
    return env


def _find_running_bot_pids() -> list[int]:
    pids: list[int] = []
    for process in psutil.process_iter(attrs=["pid", "cmdline"]):
        info = process.info
        pid = int(info.get("pid", 0))
        cmdline = info.get("cmdline") or []
        if cmdline and "python" in cmdline[0].lower() and "-m proxima.main" in " ".join(cmdline):
            pids.append(pid)
    return pids


@app.command()
def run(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Run bot in foreground (starts DB automatically)."""
    _ensure_db()
    process = subprocess.run(  # noqa: S603
        [*_python_cmd(), "-m", "proxima.main"],
        env=_build_env(verbose),
        check=False,
    )
    raise typer.Exit(process.returncode)


@app.command()
def start(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Start bot in background (starts DB automatically)."""
    if _find_running_bot_pids():
        console.print("[yellow]Bot is already running.[/yellow]")
        raise typer.Exit(0)

    _ensure_db()

    PID_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("ab") as log_handle:
        process = subprocess.Popen(  # noqa: S603
            [*_python_cmd(), "-m", "proxima.main"],
            env=_build_env(verbose),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    console.print(f"[green]Started[/green] (pid={process.pid}). Logs: [cyan]{LOG_FILE}[/cyan]")
    raise typer.Exit(0)


@app.command()
def stop() -> None:
    """Stop running bot."""
    pids = _find_running_bot_pids()
    if not pids:
        PID_FILE.unlink(missing_ok=True)
        console.print("[yellow]No running bot found.[/yellow]")
        raise typer.Exit(0)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if not _find_running_bot_pids():
            PID_FILE.unlink(missing_ok=True)
            console.print("[green]Bot stopped.[/green]")
            raise typer.Exit(0)
        time.sleep(0.2)

    for pid in _find_running_bot_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue

    PID_FILE.unlink(missing_ok=True)
    console.print("[red]Bot was force-killed.[/red]")
    raise typer.Exit(0)


@app.command()
def status() -> None:
    """Show bot status."""
    pids = _find_running_bot_pids()
    if not pids:
        console.print("Status: [yellow]stopped[/yellow]")
    else:
        console.print(f"Status: [green]running[/green] (pids={', '.join(str(p) for p in pids)})")
    raise typer.Exit(0)


@app.command()
def setup() -> None:
    """Interactive .env setup wizard."""
    run_setup_wizard()
    raise typer.Exit(0)


def main_cli() -> None:
    app(prog_name=Path(sys.argv[0]).name)


if __name__ == "__main__":
    main_cli()

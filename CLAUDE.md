# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Proxima is a self-hosted Telegram bot that proxies between Telegram users and Claude Code via the Agent SDK. Users interact through Telegram commands and messages; the bot manages projects (directories), sessions, and tool permissions.

**Stack:** Python 3.12+, aiogram, SQLAlchemy + asyncpg, claude-agent-sdk, structlog, typer, uv.

## Commands

```bash
proxima run [-v]    # Run bot in foreground (auto-starts DB, runs migrations)
proxima start [-v]  # Start bot in background
proxima stop        # Graceful shutdown
proxima status      # Show running/stopped state
proxima setup       # Interactive .env wizard
```

`-v` / `--verbose` enables debug logging (`LOG_LEVEL=debug`).

Poe tasks (via `uv run poe <task>`):
```bash
poe start     # proxima run
poe stop      # proxima stop
poe test      # pytest -q
poe lint      # ruff check .
poe format    # ruff format .
```

To run a single test file: `uv run pytest tests_py/test_something.py`

## Environment & Setup

Copy `.env.example` → `.env`. Required variables:
- `TELEGRAM_BOT_TOKEN`, `ALLOWED_USER_IDS` (comma-separated Telegram user IDs), `DATABASE_URL`
- `WORK_DIR` — base directory for projects (defaults to cwd)
- `OPENAI_API_KEY` — optional, enables voice transcription via Whisper
- `WHISPER_LANGUAGE` — ISO-639-1 language code for transcription (optional; auto-detect if unset)
- `ANTHROPIC_API_KEY` — optional (SDK may use its own env)
- `LOG_LEVEL` — debug/info/warn/error (default: info)
- `SESSION_TIMEOUT` — session idle timeout in minutes (default: 30)

PostgreSQL and DB migrations start automatically with `proxima run` / `proxima start`.

Install deps: `uv sync --dev`

## Architecture

```
proxima/
  main.py              # Entry: App class, migrations, polling, graceful shutdown
  settings.py          # Pydantic-settings config (reads .env)
  logging.py           # structlog setup (JSON in prod, console in dev)
  lifecycle.py         # SIGINT/SIGTERM signal handlers
  services.py          # Dependency injection dataclass
  bot/
    router.py          # All command handlers + message/voice/bash/callback routing
    middlewares.py     # AuthMiddleware, ProjectResolverMiddleware
  claude/
    sdk.py             # Dynamic SDK import, iter_claude_query() async generator
    query_runner.py    # asyncio.Task registry per chat; cancel_query()
    session_manager.py # DB-backed session CRUD; resumption via claude_session_id
    stream_renderer.py # SDK events → Telegram messages (debounced 500ms, auto-split)
    permission_handler.py # Inline-button approval with 5-min timeout; Allow/Deny/Allow All
    session_watchdog.py # Auto-idle stale sessions + Telegram notifications
  commands/
    storage.py         # Custom slash command CRUD (.claude/commands/*.md)
  db/
    engine.py          # AsyncEngine + AsyncSession factory (pool_size=10)
    models.py          # SQLAlchemy ORM models (Project, Session, MCPConfig)
    migrate.py         # Raw SQL migrations (idempotent, runs on startup)
    repositories/
      project.py       # Project CRUD
      session.py       # Session CRUD + touchActivity
      mcp_config.py    # MCP server config per project
  telegram/
    message_sender.py  # Edit-then-split strategy: edits up to 4000 chars, then new messages
    keyboards.py       # Inline button layout for permission/mode requests
  utils/
    queue.py           # SequentialQueue: dict[project_id, deque], one active task per project
    markdown_to_html.py # Markdown → Telegram HTML converter
  voice/
    transcribe.py      # OpenAI Whisper API (optional; skipped if no OPENAI_API_KEY)
    ffmpeg.py          # Telegram voice download → temp OGG → MP3
  cli/
    tool.py            # Typer CLI (run/start/stop/status/setup)
    setup.py           # Interactive setup wizard
```

## Key Patterns

**Sequential queue per project**: Every incoming message is enqueued via `SequentialQueue` keyed by `project_id`. This prevents concurrent Claude queries on the same project.

**Claude session lifecycle**:
1. `session_manager.py` finds or creates a DB session for the active project.
2. `iter_claude_query()` calls the SDK's `query()` with `resume` session ID if one exists.
3. The `init` event from the SDK stream carries the actual `session_id`, which is stored back in the DB.
4. On `/reset`, the session is closed; next message starts a fresh session.
5. `SessionWatchdog` runs every 60s; marks sessions as `idle` after `SESSION_TIMEOUT` minutes of inactivity and notifies the user. Next message auto-resumes the idle session.

**Custom slash commands**: `/cmd` manages `.md` files in `~/.claude/commands/` (user scope) and `<project>/.claude/commands/` (project scope). Commands are invoked via `/user:<name>` or `/project:<name>` — the bot substitutes `$ARGUMENTS` and forwards the prompt to Claude.

**Streaming to Telegram**: `stream_renderer.py` accumulates text from SDK messages and edits the Telegram message every 500ms. Tool use events emit status lines. Long responses are auto-split at 4000 chars.

**Permission system**: When the SDK triggers `can_use_tool`, `permission_handler.py` sends an inline keyboard to Telegram. The bot waits (up to 5 min) for the user's callback via `asyncio.Future`. "Allow All" toggles session-level bypass. Per-project `permission_mode` can be `bypassPermissions`, `default`, `acceptEdits`, `dontAsk`, or `plan`.

**Middleware stack**: AuthMiddleware (checks `ALLOWED_USER_IDS`) → ProjectResolverMiddleware (loads/creates active project) → Router handlers.

**Database schema** (three tables): `projects` (chat→directory mapping, active flag, permission_mode), `sessions` (project FK, claude_session_id, status), `mcp_configs` (project FK, server JSON, enabled flag).

## Testing

Unit tests in `tests_py/*.py` use pytest with pytest-asyncio (auto mode). Run all tests: `uv run pytest -q`. Run single file: `uv run pytest tests_py/test_something.py`.

## Code Quality

```bash
uv run ruff check .     # Linting (E, F, I, B, UP, ASYNC rules)
uv run ruff format .    # Formatting
uv run mypy proxima/    # Strict type checking
```

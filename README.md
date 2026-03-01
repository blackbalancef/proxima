```
                                                        .
██████╗ ██████╗  ██████╗ ██╗  ██╗██╗███╗   ███╗ █████╗  \   /
██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██║████╗ ████║██╔══██╗ .\-./
██████╔╝██████╔╝██║   ██║ ╚███╔╝ ██║██╔████╔██║███████║ -===-
██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗ ██║██║╚██╔╝██║██╔══██║ '/=\'
██║     ██║  ██║╚██████╔╝██╔╝ ██╗██║██║ ╚═╝ ██║██║  ██║ /   \
╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝'
```

# Proxima

Self-hosted Telegram bot that gives you Claude Code right inside Telegram.
Send a message — get a response from Claude with full tool use, file editing, and bash execution.

## Features

- Text, voice messages, and bash output forwarded to Claude Code
- Multi-project management (each chat can have its own working directory)
- Session persistence with auto-resume
- Streaming responses with live editing in Telegram
- Tool permission control (inline buttons: Allow / Deny / Allow All)
- MCP server configuration per project
- Custom slash commands
- Voice transcription via OpenAI Whisper (optional)

## Quick Start

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for PostgreSQL)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) logged in (`claude` command must work)

### 2. Clone and install

```bash
git clone https://github.com/anthropics/proxima.git
cd proxima
uv sync --dev
```

### 3. Configure

```bash
proxima setup
```

This runs an interactive wizard that creates `.env`. You need:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | From [@BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_IDS` | yes | Your Telegram user ID (comma-separated for multiple) |
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `WORK_DIR` | no | Base directory for projects (default: `./projects/`) |
| `OPENAI_API_KEY` | no | Enables voice transcription |
| `WHISPER_LANGUAGE` | no | ISO-639-1 code (e.g. `ru`, `en`). Auto-detect if unset |
| `SESSION_TIMEOUT` | no | Session idle timeout in minutes (default: 30) |

### 4. Run

```bash
proxima run
```

This starts PostgreSQL via Docker, runs migrations, and launches the bot.
Open your bot in Telegram and send any message.

## CLI

```bash
proxima run [-v]     # Run in foreground (auto-starts DB + migrations)
proxima start [-v]   # Start in background
proxima stop         # Graceful shutdown
proxima status       # Show running/stopped
proxima setup        # Interactive .env wizard
```

`-v` enables debug logging.

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + project list |
| `/new_prox <name>` | Create a new project |
| `/projects_prox` | List all projects |
| `/switch_prox` | Switch active project |
| `/reset_prox` | Reset current session |
| `/cancel_prox` | Cancel running query |
| `/mode_prox` | Toggle plan/execute mode |
| `/permissions_prox` | Change permission preset |
| `/mcp_prox` | Configure MCP servers |
| `/memory_prox` | Edit project CLAUDE.md |
| `/cmd_prox` | Manage custom slash commands |
| `/help_prox` | Show all commands |

## Development

```bash
uv run pytest -q        # Run tests
uv run ruff check .     # Lint
uv run ruff format .    # Format
uv run mypy proxima/    # Type check
```

## License

MIT

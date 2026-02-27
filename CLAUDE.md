# Proxima — Claude Code Telegram Bot

## Project Overview
Self-hosted Telegram bot that proxies between Telegram and Claude Code via the Agent SDK.

## Tech Stack
- TypeScript 5.5+, Node.js 22 LTS, pnpm
- grammY (Telegram), @anthropic-ai/claude-agent-sdk (Claude Code)
- PostgreSQL 16 + Kysely (later phases), Pino (logging)
- Zod (config validation), tsx (dev runner), vitest (tests)

## Commands
- `pnpm dev` — run with watch mode
- `pnpm start` — run without watch
- `pnpm typecheck` — type checking

## Architecture
- `src/bot/` — grammY bot, handlers, commands, middleware
- `src/claude/` — Agent SDK integration (sessions, streaming, permissions)
- `src/db/` — Kysely DB layer (Phase 1c+)
- `src/telegram/` — message sending utilities
- `src/voice/` — voice transcription (Phase 4)
- `src/utils/` — logger, queue, lifecycle

## Key Patterns
- ESM modules (`"type": "module"` in package.json)
- Zod-validated config from environment
- Per-project sequential message queue
- Agent SDK `query()` with AsyncGenerator streaming
- Session resumption via `session_id` from init messages

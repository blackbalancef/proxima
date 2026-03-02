from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Any

import psutil
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError

from proxima.claude.permission_handler import find_permission_handler, get_permission_handler
from proxima.claude.query_runner import cancel_query, clear_task, set_active_task
from proxima.claude.sdk import PermissionHook, iter_claude_query
from proxima.claude.stream_renderer import StreamRenderer
from proxima.db.models import Project
from proxima.lifecycle import request_restart
from proxima.logging import get_logger
from proxima.services import Services
from proxima.telegram.keyboards import (
    build_mode_keyboard,
    build_model_keyboard,
    build_project_keyboard,
    build_update_keyboard,
)
from proxima.telegram.message_sender import MessageSender
from proxima.utils.queue import message_queue
from proxima.voice.ffmpeg import cleanup_temp, download_to_temp, ogg_to_mp3
from proxima.voice.transcribe import transcribe_audio

logger = get_logger(__name__)

APP_START_TS = time.monotonic()
MAX_OUTPUT = 4000
_BOT_REPO_DIR = Path(__file__).resolve().parent.parent.parent
_update_lock = asyncio.Lock()

PERMISSION_PRESETS: dict[str, dict[str, str]] = {
    "plan": {
        "label": "Plan Only",
        "description": "Read-only mode.",
    },
    "default": {
        "label": "Default",
        "description": "Prompt for dangerous operations.",
    },
    "acceptEdits": {
        "label": "Accept Edits",
        "description": "Auto-accept edits, ask for shell commands.",
    },
    "dontAsk": {
        "label": "Don't Ask",
        "description": "No prompts for tool permission requests.",
    },
    "bypassPermissions": {
        "label": "Bypass All",
        "description": "Skip all permission checks.",
    },
}


DEFAULT_MODEL = "claude-sonnet-4-6"

MODEL_PRESETS: dict[str, dict[str, str]] = {
    "claude-opus-4-6": {"label": "Opus", "short": "opus"},
    "claude-sonnet-4-6": {"label": "Sonnet", "short": "sonnet"},
    "claude-haiku-4-5": {"label": "Haiku", "short": "haiku"},
}
SHORT_TO_MODEL: dict[str, str] = {v["short"]: k for k, v in MODEL_PRESETS.items()}


def build_router(services: Services) -> Router:
    router = Router(name="proxima")

    @router.message(Command("start"))
    async def start_command(message: Message) -> None:
        projects = await services.projects.find_all_by_chat(message.chat.id)
        lines = [
            "Welcome to Proxima!",
            "",
            "Send text to forward to Claude Code.",
            "Send voice to transcribe and forward.",
            "Prefix with ! to run shell commands directly.",
            "",
            "Use /help_prox for all commands.",
        ]
        if projects:
            lines.extend(["", f"Projects ({len(projects)}):"])
            keyboard_data: list[dict[str, int | str]] = [
                {"id": p.id, "name": p.name} for p in projects
            ]
            await message.answer(
                "\n".join(lines), reply_markup=build_project_keyboard(keyboard_data)
            )
        else:
            lines.extend(["", "No projects yet. Use /new_prox <name> to create one."])
            await message.answer("\n".join(lines))

    @router.message(Command("help_prox"))
    async def help_command(message: Message) -> None:
        claude_cmds = sorted(services.claude_slash_commands)
        if claude_cmds:
            claude_section = [
                "Claude commands (forwarded to SDK):",
                "  " + "  ".join(f"/{c}" for c in claude_cmds),
            ]
        else:
            claude_section = [
                "Claude commands: send any message first to discover.",
            ]

        await message.answer(
            "\n".join(
                [
                    "Proxima - Claude Code Telegram Bot",
                    "",
                    "Text → Claude Code",
                    "Voice → Whisper + Claude Code",
                    "! <command> → direct shell",
                    "",
                    *claude_section,
                    "",
                    "Bot commands:",
                    " Projects:",
                    "  /new_prox <name> [dir]",
                    "  /clone_prox <url> [name]",
                    "  /projects_prox",
                    "  /rename_prox <old> <new>",
                    "  /delete_prox <name>",
                    "  /sync_prox",
                    "",
                    " Sessions:",
                    "  /thread_prox <name>",
                    "  /reset_prox",
                    "  /close_prox",
                    "  /cancel_prox",
                    "  /info_prox",
                    "",
                    " Settings:",
                    "  /model_prox [opus|sonnet|haiku]",
                    "  /mode_prox [plan|execute]",
                    "  /permissions_prox [mode]",
                    "  /mcp_prox",
                    "  /memory_prox",
                    "",
                    " Custom commands:",
                    "  /cmd_prox",
                    "",
                    " Admin:",
                    "  /server_prox",
                    "  /users_prox",
                    "  /config_prox",
                    "  /update_prox",
                ]
            )
        )

    @router.message(Command("cancel_prox"))
    async def cancel_command(message: Message, thread_id: int | None) -> None:
        chat_id = message.chat.id
        cancelled = cancel_query((chat_id, thread_id))
        if cancelled:
            await message.answer("Cancelling current query...")
        else:
            await message.answer("No active query to cancel.")

    @router.message(Command("new_prox"))
    async def new_project_command(message: Message, project: Project) -> None:  # noqa: ARG001
        args = _command_args(message)
        if not args:
            await message.answer(
                "Usage: /new_prox <project-name> [directory]\n\n"
                "Example:\n/new_prox myapp /path/to/myapp\n/new_prox myapp"
            )
            return

        parts = shlex.split(args)
        name = parts[0]
        directory = parts[1] if len(parts) > 1 else str(services.settings.work_dir)
        assert message.bot is not None
        bot = message.bot
        chat_id = message.chat.id

        try:
            created = await services.projects.create(
                {
                    "telegram_chat_id": chat_id,
                    "name": name,
                    "directory": directory,
                    "is_active": False,
                    "permission_mode": "bypassPermissions",
                }
            )
            await services.projects.set_active(chat_id, created.id)

            try:
                await _create_project_thread(bot, chat_id, created, services)
            except Exception:  # noqa: BLE001
                # Not a forum / supergroup — fall back to regular message
                await message.answer(f'Project "{name}" created and activated.\nDir: {directory}')
        except IntegrityError:
            await message.answer(f'Project "{name}" already exists. Use /thread_prox {name}')

    @router.message(Command("clone_prox"))
    async def clone_project_command(message: Message, project: Project) -> None:  # noqa: ARG001
        args = _command_args(message).strip()
        if not args:
            await message.answer(
                "Usage: /clone_prox <git-url> [project-name]\n\n"
                "Example:\n"
                "/clone_prox https://github.com/user/repo\n"
                "/clone_prox git@github.com:user/repo.git myapp"
            )
            return

        parts = shlex.split(args)
        url = parts[0]
        # Derive project name from URL if not provided
        if len(parts) > 1:
            name = parts[1]
        else:
            name = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
            if name.endswith(".git"):
                name = name[:-4]

        directory = str(Path(str(services.settings.work_dir)) / name)

        if await asyncio.to_thread(os.path.isdir, directory):
            await message.answer(
                f'Directory "{directory}" already exists.\n'
                f"Use /new_prox {name} {directory} to create a project from it."
            )
            return

        status = await message.answer(f"Cloning {url}...")
        assert message.bot is not None
        bot = message.bot

        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                url,
                directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)

            if process.returncode != 0:
                error = (stderr or stdout).decode("utf-8", errors="ignore").strip()
                await bot.edit_message_text(
                    chat_id=status.chat.id,
                    message_id=status.message_id,
                    text=f"Clone failed:\n{error[:2000]}",
                )
                return

            created = await services.projects.create(
                {
                    "telegram_chat_id": message.chat.id,
                    "name": name,
                    "directory": directory,
                    "is_active": False,
                    "permission_mode": "bypassPermissions",
                }
            )
            await services.projects.set_active(message.chat.id, created.id)
            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f'Cloned and activated "{name}"\nDir: {directory}',
            )
        except TimeoutError:
            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text="Clone timed out (5 min limit).",
            )
        except IntegrityError:
            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f'Project "{name}" already exists. Use /thread_prox {name}',
            )

    @router.message(Command("projects_prox"))
    async def list_projects_command(message: Message, project: Project) -> None:  # noqa: ARG001
        projects = await services.projects.find_all_by_chat(message.chat.id)
        if not projects:
            await message.answer("No projects. Use /new_prox to create one.")
            return

        lines = [f"  {p.name} - {p.directory}" for p in projects]
        await message.answer(f"Projects:\n\n{'\n'.join(lines)}")

    @router.message(Command("delete_prox"))
    async def delete_project_command(message: Message, project: Project) -> None:  # noqa: ARG001
        name = _command_args(message).strip()
        if not name:
            await message.answer("Usage: /delete_prox <project-name>")
            return

        projects = await services.projects.find_all_by_chat(message.chat.id)
        target = next((p for p in projects if p.name == name), None)
        if target is None:
            await message.answer(f'Project "{name}" not found.')
            return

        if target.name == "default":
            await message.answer("Cannot delete the default project.")
            return

        await services.projects.delete_by_id(target.id)
        await message.answer(f'Project "{name}" deleted.')

    @router.message(Command("sync_prox"))
    async def sync_projects_command(message: Message, project: Project) -> None:  # noqa: ARG001
        assert message.bot is not None
        bot = message.bot
        chat_id = message.chat.id
        status_msg = await message.answer("Syncing projects...")

        all_projects = await services.projects.find_all()
        work_dir = str(services.settings.work_dir.resolve())

        # --- Prune dead projects ---
        pruned: list[str] = []
        prune_errors: list[str] = []
        for proj in all_projects:
            if proj.name == "default":
                continue
            exists = await asyncio.to_thread(os.path.isdir, proj.directory)
            if exists:
                continue
            # Delete forum topics for this project
            threads = await services.sessions.find_threads_by_project(proj.id)
            for t_chat_id, t_thread_id in threads:
                try:
                    await bot.delete_forum_topic(t_chat_id, t_thread_id)
                except Exception:  # noqa: BLE001
                    pass
            try:
                await services.projects.delete_by_id(proj.id)
                pruned.append(f"{proj.name} ({proj.directory})")
            except Exception as exc:  # noqa: BLE001
                prune_errors.append(f"{proj.name}: {exc}")

        # --- Discover new directories ---
        remaining = await services.projects.find_all()
        dirs = [p.directory for p in remaining]
        tracked_dirs = set(await asyncio.to_thread(lambda: [os.path.realpath(d) for d in dirs]))

        added: list[str] = []
        skipped: list[str] = []

        def _list_subdirs(parent: str) -> list[tuple[str, str]]:
            """Return (name, resolved_path) for subdirectories of parent."""
            base = Path(parent)
            if not base.is_dir():
                return []
            return sorted(
                (entry.name, str(entry.resolve())) for entry in base.iterdir() if entry.is_dir()
            )

        subdirs = await asyncio.to_thread(_list_subdirs, work_dir)
        for name, resolved in subdirs:
            if resolved in tracked_dirs:
                continue
            try:
                created = await services.projects.create(
                    {
                        "telegram_chat_id": chat_id,
                        "name": name,
                        "directory": resolved,
                        "is_active": False,
                        "permission_mode": "bypassPermissions",
                    }
                )
                try:
                    await _create_project_thread(bot, chat_id, created, services)
                except Exception:  # noqa: BLE001
                    pass  # Not a forum chat
                added.append(name)
            except IntegrityError:
                skipped.append(name)

        # --- Build report ---
        lines = ["Sync complete."]
        if pruned:
            lines.append(f"\nRemoved ({len(pruned)}):")
            lines.extend(f"  - {p}" for p in pruned)
        if added:
            lines.append(f"\nAdded ({len(added)}):")
            lines.extend(f"  - {a}" for a in added)
        if skipped:
            lines.append(f"\nSkipped ({len(skipped)}):")
            lines.extend(f"  - {s}" for s in skipped)
        if prune_errors:
            lines.append(f"\nErrors ({len(prune_errors)}):")
            lines.extend(f"  - {e}" for e in prune_errors)
        if not pruned and not added and not skipped:
            lines.append("\nNo changes needed.")

        await bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="\n".join(lines),
        )

    @router.message(Command("rename_prox"))
    async def rename_project_command(message: Message, project: Project) -> None:  # noqa: ARG001
        parts = _command_args(message).split()
        if len(parts) < 2:
            await message.answer("Usage: /rename_prox <old-name> <new-name>")
            return

        old_name, new_name = parts[0], parts[1]
        projects = await services.projects.find_all_by_chat(message.chat.id)
        target = next((p for p in projects if p.name == old_name), None)
        if target is None:
            await message.answer(f'Project "{old_name}" not found.')
            return

        await services.projects.update(target.id, {"name": new_name})
        await message.answer(f'Project renamed: "{old_name}" -> "{new_name}"')

    @router.message(Command("thread_prox"))
    async def thread_command(message: Message, project: Project) -> None:  # noqa: ARG001
        assert message.bot is not None
        bot = message.bot
        chat_id = message.chat.id
        name = _command_args(message).strip()

        if not name:
            await message.answer("Usage: /thread_prox <project-name>")
            return

        projects = await services.projects.find_all_by_chat(chat_id)
        target = next((p for p in projects if p.name == name), None)
        if target is None:
            await message.answer(f'Project "{name}" not found. Use /projects_prox to list.')
            return

        try:
            await _create_project_thread(bot, chat_id, target, services)
        except Exception as exc:  # noqa: BLE001
            await message.answer(
                f"Cannot create topic: {exc}\n\nMake sure this is a supergroup with Topics enabled."
            )

    @router.message(Command("reset_prox"))
    async def reset_session_command(
        message: Message, project: Project, thread_id: int | None
    ) -> None:
        if thread_id is not None:
            await services.session_manager.reset_thread_session(message.chat.id, thread_id)
        else:
            await services.session_manager.reset_session(project.id)
        await message.answer(
            f'Session reset for project "{project.name}".\n'
            "Next message starts a fresh conversation."
        )

    @router.message(Command("close_prox"))
    async def close_session_command(
        message: Message, project: Project, thread_id: int | None
    ) -> None:
        assert message.bot is not None
        bot = message.bot
        chat_id = message.chat.id

        if thread_id is not None:
            sess = await services.sessions.find_latest_by_thread(chat_id, thread_id)
            if sess:
                await services.sessions.delete_by_id(sess.id)
            try:
                await bot.delete_forum_topic(chat_id, thread_id)
            except Exception:  # noqa: BLE001
                await message.answer("Session deleted, but could not remove the topic.")
        else:
            sess = await services.sessions.find_active_by_project(project.id)
            if sess is None:
                await message.answer("No active session to close.")
                return
            tid = sess.message_thread_id
            await services.sessions.delete_by_id(sess.id)
            if tid is not None:
                try:
                    await bot.delete_forum_topic(chat_id, tid)
                except Exception:  # noqa: BLE001
                    pass
            await message.answer("Session closed and deleted.")

    @router.message(Command("info_prox"))
    async def info_command(message: Message, project: Project, thread_id: int | None) -> None:
        if thread_id is not None:
            session = await services.sessions.find_active_by_thread(message.chat.id, thread_id)
        else:
            session = await services.sessions.find_active_by_project(project.id)
        lines = [
            f"Project: {project.name}",
            f"Directory: {project.directory}",
            f"Permission mode: {project.permission_mode}",
            "",
        ]
        if thread_id is not None:
            lines.append(f"Thread: {thread_id}")
        if session:
            effective_model = session.model or DEFAULT_MODEL
            model_label = MODEL_PRESETS[effective_model]["label"]
            lines.extend(
                [
                    "Session: active",
                    f"Model: {model_label}",
                    f"Claude session: {session.claude_session_id or '(not started)'}",
                    f"Last activity: {session.last_activity.isoformat()}",
                ]
            )
        else:
            lines.append("Session: none")

        await message.answer("\n".join(lines))

    @router.message(Command("model_prox"))
    async def model_command(message: Message, project: Project, thread_id: int | None) -> None:
        arg = _command_args(message).strip().lower()
        session = await services.session_manager.get_or_create(
            project.id, thread_id=thread_id, chat_id=message.chat.id
        )
        if arg:
            model_id = SHORT_TO_MODEL.get(arg) or (arg if arg in MODEL_PRESETS else None)
            if not model_id:
                await message.answer(f"Unknown model: {arg}\n\nAvailable: opus, sonnet, haiku")
                return
            await services.session_manager.update_model(session.db_id, model_id)
            label = MODEL_PRESETS[model_id]["label"]
            await message.answer(f"Model set to: {label}")
            return

        current = session.model or DEFAULT_MODEL
        label = MODEL_PRESETS[current]["label"]
        await message.answer(
            f"Current model: {label}\n\nSelect model:",
            reply_markup=build_model_keyboard(current),
        )

    @router.message(Command("mode_prox"))
    async def mode_command(message: Message, project: Project) -> None:
        arg = _command_args(message).strip()
        if arg == "plan":
            await services.projects.update(project.id, {"permission_mode": "plan"})
            await message.answer("Mode: Plan\nClaude will analyze but not modify files.")
            return
        if arg == "execute":
            await services.projects.update(project.id, {"permission_mode": "bypassPermissions"})
            await message.answer("Mode: Execute\nClaude can modify files and run commands.")
            return

        current = "Plan" if project.permission_mode == "plan" else "Execute"
        await message.answer(
            f"Current mode: {current}\n\nSelect mode:",
            reply_markup=build_mode_keyboard(),
        )

    @router.message(Command("permissions_prox"))
    async def permissions_command(message: Message, project: Project) -> None:
        arg = _command_args(message).strip()
        if arg and arg in PERMISSION_PRESETS:
            await services.projects.update(project.id, {"permission_mode": arg})
            preset = PERMISSION_PRESETS[arg]
            await message.answer(
                f"Permission mode set to: {preset['label']}\n{preset['description']}"
            )
            return

        current = PERMISSION_PRESETS.get(project.permission_mode)
        lines = [
            f"Current mode: {(current or {'label': project.permission_mode})['label']}",
            (current or {"description": ""})["description"],
            "",
            "Modes:",
        ]
        for key, preset in PERMISSION_PRESETS.items():
            prefix = "-> " if key == project.permission_mode else "   "
            lines.append(f"{prefix}{key}: {preset['description']}")
        await message.answer("\n".join(lines))

    @router.message(Command("mcp_prox"))
    async def mcp_command(message: Message, project: Project) -> None:
        parts = _command_args(message).split()
        action = parts[0] if parts else ""

        if not action:
            configs = await services.mcp_configs.find_by_project(project.id)
            if not configs:
                await message.answer(
                    "No MCP servers configured.\n\nUsage: /mcp_prox add <name> <command> [args...]"
                )
                return
            lines: list[str] = []
            for cfg in configs:
                status = "enabled" if cfg.enabled else "disabled"
                config_json = json.loads(cfg.config_json)
                lines.append(f"[{status}] {cfg.server_name} - {config_json.get('command', '')}")
            await message.answer(f"MCP servers:\n\n{'\n'.join(lines)}")
            return

        if action == "add":
            if len(parts) < 3:
                await message.answer(
                    "Usage: /mcp_prox add <name> <command> [args...]\n\n"
                    "Example: /mcp_prox add playwright npx @playwright/mcp@latest"
                )
                return
            name, command = parts[1], parts[2]
            args = parts[3:]
            await services.mcp_configs.upsert(
                {
                    "project_id": project.id,
                    "server_name": name,
                    "config_json": json.dumps({"command": command, "args": args}),
                    "enabled": True,
                }
            )
            await message.answer(f'MCP server "{name}" added.\nCommand: {command} {" ".join(args)}')
            return

        if action == "remove":
            if len(parts) < 2:
                await message.answer("Usage: /mcp_prox remove <name>")
                return
            name = parts[1]
            configs = await services.mcp_configs.find_by_project(project.id)
            target = next((cfg for cfg in configs if cfg.server_name == name), None)
            if not target:
                await message.answer(f'MCP server "{name}" not found.')
                return
            await services.mcp_configs.delete_by_id(target.id)
            await message.answer(f'MCP server "{name}" removed.')
            return

        if action == "toggle":
            if len(parts) < 2:
                await message.answer("Usage: /mcp_prox toggle <name>")
                return
            name = parts[1]
            configs = await services.mcp_configs.find_by_project(project.id)
            target = next((cfg for cfg in configs if cfg.server_name == name), None)
            if not target:
                await message.answer(f'MCP server "{name}" not found.')
                return
            await services.mcp_configs.toggle(target.id, not target.enabled)
            status = "enabled" if not target.enabled else "disabled"
            await message.answer(f'MCP server "{name}" {status}.')
            return

        await message.answer(
            "Unknown action. Use: /mcp_prox, /mcp_prox add, /mcp_prox remove, /mcp_prox toggle"
        )

    @router.message(Command("memory_prox"))
    async def memory_command(message: Message, project: Project) -> None:
        claude_md_path = Path(project.directory) / "CLAUDE.md"
        parts = _command_args(message).split()
        action = parts[0] if parts else ""

        if not action:
            try:
                content = claude_md_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                await message.answer(
                    "No CLAUDE.md found in project directory.\n\n"
                    "Use /memory_prox set <content> to create one."
                )
                return
            truncated = content[:3500] + "\n\n... (truncated)" if len(content) > 3500 else content
            await message.answer(f"CLAUDE.md:\n\n{truncated}")
            return

        if action == "set":
            content_parts = _command_args(message).split(" ", 1)
            if len(content_parts) < 2 or not content_parts[1].strip():
                await message.answer("Usage: /memory_prox set <content>")
                return
            claude_md_path.parent.mkdir(parents=True, exist_ok=True)
            claude_md_path.write_text(content_parts[1], encoding="utf-8")
            await message.answer("CLAUDE.md updated.")
            return

        if action == "append":
            content_parts = _command_args(message).split(" ", 1)
            if len(content_parts) < 2 or not content_parts[1].strip():
                await message.answer("Usage: /memory_prox append <content>")
                return
            existing = claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
            claude_md_path.parent.mkdir(parents=True, exist_ok=True)
            claude_md_path.write_text(existing + "\n" + content_parts[1], encoding="utf-8")
            await message.answer("Content appended to CLAUDE.md.")
            return

        await message.answer(
            "Usage: /memory_prox, /memory_prox set <content>, /memory_prox append <content>"
        )

    @router.message(Command("cmd_prox"))
    async def cmd_command(message: Message, project: Project) -> None:
        args = _command_args(message).strip()

        if not args:
            commands = services.command_storage.list_all(project.directory)
            if not commands:
                await message.answer(
                    "No custom commands.\n\n"
                    "Usage: /cmd_prox new <scope> <name>\n"
                    "Scopes: user, project"
                )
                return
            lines: list[str] = []
            for cmd in commands:
                lines.append(f"  [{cmd.scope}] {cmd.name} - {cmd.description[:60]}")
            await message.answer(f"Custom commands:\n\n{'\n'.join(lines)}")
            return

        parts = args.split()
        action = parts[0]

        if action == "new":
            if len(parts) < 3:
                await message.answer(
                    "Usage: /cmd_prox new <scope> <name>\n"
                    "Scopes: user, project\n\n"
                    "After creating, reply with the command content."
                )
                return
            scope = parts[1]
            if scope not in ("user", "project"):
                await message.answer("Scope must be 'user' or 'project'.")
                return
            name = parts[2]
            content = " ".join(parts[3:]) if len(parts) > 3 else ""
            if not content:
                await message.answer(
                    f"Send the content for command '{name}' ({scope}) in the next message.\n"
                    "Use $ARGUMENTS as a placeholder for arguments."
                )
                return
            path = services.command_storage.save(name, scope, project.directory, content)
            prefix = "user" if scope == "user" else "project"
            await message.answer(f"Command saved: /{prefix}:{name}\nPath: {path}")
            return

        if action == "show":
            if len(parts) < 2:
                await message.answer("Usage: /cmd_prox show <name>")
                return
            name = parts[1]
            for scope in ("project", "user"):
                body = services.command_storage.get(name, scope, project.directory)
                if body is not None:
                    if len(body) > 3500:
                        truncated = body[:3500] + "\n... (truncated)"
                    else:
                        truncated = body
                    await message.answer(f"[{scope}] {name}:\n\n{truncated}")
                    return
            await message.answer(f"Command '{name}' not found.")
            return

        if action == "delete":
            if len(parts) < 2:
                await message.answer("Usage: /cmd_prox delete <name>")
                return
            name = parts[1]
            scope = parts[2] if len(parts) > 2 else ""
            if scope:
                deleted = services.command_storage.delete(name, scope, project.directory)
            else:
                deleted = services.command_storage.delete(
                    name, "project", project.directory
                ) or services.command_storage.delete(name, "user", project.directory)
            if deleted:
                await message.answer(f"Command '{name}' deleted.")
            else:
                await message.answer(f"Command '{name}' not found.")
            return

        await message.answer(
            "Usage: /cmd_prox, /cmd_prox new, /cmd_prox show <name>, /cmd_prox delete <name>"
        )

    @router.message(Command("server_prox"))
    async def server_command(message: Message) -> None:
        mem = psutil.virtual_memory()
        mem_total = mem.total / (1024**3)
        mem_available = mem.available / (1024**3)
        uptime = _format_uptime(time.monotonic() - APP_START_TS)
        await message.answer(
            "\n".join(
                [
                    f"Host: {os.uname().nodename}",
                    f"Platform: {os.uname().sysname} {os.uname().release}",
                    f"CPUs: {os.cpu_count() or 0}",
                    f"Memory: {mem_available:.1f}/{mem_total:.1f} GB free",
                    f"Python: {sys.version.split()[0]}",
                    f"Uptime: {uptime}",
                    f"PID: {os.getpid()}",
                ]
            )
        )

    @router.message(Command("config_prox"))
    async def config_command(message: Message) -> None:
        s = services.settings
        whisper_status = "enabled" if s.openai_api_key else "disabled"
        try:
            from claude_agent_sdk import __version__ as sdk_version
        except Exception:
            sdk_version = "unknown"
        await message.answer(
            "\n".join(
                [
                    f"Allowed users: {len(s.allowed_user_ids)}",
                    f"Projects dir: {s.work_dir}",
                    f"Whisper: {whisper_status}",
                    f"Log level: {s.log_level}",
                    f"Claude SDK: {sdk_version}",
                ]
            )
        )

    @router.message(Command("users_prox"))
    async def users_command(message: Message) -> None:
        user_ids = services.settings.allowed_user_ids
        lines = [str(user_id) for user_id in user_ids]
        await message.answer(
            "\n".join(
                [
                    "Allowed users (from ALLOWED_USER_IDS):",
                    "",
                    *lines,
                    "",
                    "Edit .env to add/remove users, then restart.",
                ]
            )
        )

    @router.callback_query(F.data.startswith("perm:"))
    async def permission_callback(callback: CallbackQuery) -> None:
        data = callback.data or ""
        if callback.message:
            thread_id = callback.message.message_thread_id  # type: ignore[union-attr]
            handler = find_permission_handler(callback.message.chat.id, thread_id)
        else:
            handler = None
        if handler:

            async def answer_fn() -> None:
                await callback.answer()

            handled = await handler.handle_callback(data, answer_fn)
            if handled:
                return
        await callback.answer("Request expired")

    @router.callback_query(F.data.startswith("project:thread:"))
    async def create_thread_callback(callback: CallbackQuery) -> None:
        msg = callback.message
        if not msg or not callback.message:
            await callback.answer()
            return

        parts = (callback.data or "").split(":")
        if len(parts) < 3:
            await callback.answer()
            return

        project_id = int(parts[2])
        project = await services.projects.find_by_id(project_id)
        if not project:
            await callback.answer()
            return

        bot = callback.bot
        chat_id = msg.chat.id
        try:
            await _create_project_thread(bot, chat_id, project, services)
            await callback.answer(f"Thread created for {project.name}")
        except Exception as exc:  # noqa: BLE001
            await callback.answer(f"Cannot create topic: {exc}"[:200])

    @router.callback_query(F.data.startswith("mode:"))
    async def mode_callback(callback: CallbackQuery, project: Project) -> None:
        data = callback.data or ""
        mode = data.split(":", maxsplit=1)[1] if ":" in data else ""
        perm_mode = "plan" if mode == "plan" else "bypassPermissions"
        await services.projects.update(project.id, {"permission_mode": perm_mode})

        label = "Plan" if mode == "plan" else "Execute"
        await callback.answer(f"Mode: {label}")
        msg = callback.message
        if msg and hasattr(msg, "edit_text"):
            await msg.edit_text(f"Mode set to: {label}")

    @router.callback_query(F.data.startswith("model:"))
    async def model_callback(
        callback: CallbackQuery, project: Project, thread_id: int | None
    ) -> None:
        data = callback.data or ""
        model_id = data.split(":", maxsplit=1)[1] if ":" in data else ""
        if model_id not in MODEL_PRESETS:
            await callback.answer("Unknown model")
            return

        chat_id = callback.message.chat.id if callback.message else 0
        session = await services.session_manager.get_or_create(
            project.id, thread_id=thread_id, chat_id=chat_id
        )
        await services.session_manager.update_model(session.db_id, model_id)
        label = MODEL_PRESETS[model_id]["label"]
        await callback.answer(f"Model: {label}")
        msg = callback.message
        if msg and hasattr(msg, "edit_text"):
            await msg.edit_text(f"Model set to: {label}")

    @router.message(F.voice)
    async def voice_handler(message: Message, project: Project, thread_id: int | None) -> None:
        if not message.voice or not message.bot:
            return

        bot = message.bot
        status = await message.answer("Transcribing...")
        ogg_path: Path | None = None
        mp3_path: Path | None = None

        try:
            file = await bot.get_file(message.voice.file_id)
            if not file.file_path:
                raise RuntimeError("Telegram did not return file path for voice message")

            file_url = f"https://api.telegram.org/file/bot{services.settings.telegram_bot_token}/{file.file_path}"
            ogg_path = await download_to_temp(file_url, "ogg")
            mp3_path = await ogg_to_mp3(ogg_path)
            text = await transcribe_audio(
                mp3_path,
                services.settings.openai_api_key,
                language=services.settings.whisper_language,
            )

            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f'Transcribed: "{text}"',
            )
            await _enqueue_prompt(message, text, project, services, thread_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("voice_processing_failed", error=str(exc))
            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f"Voice error: {exc}",
            )
        finally:
            if ogg_path:
                await cleanup_temp(ogg_path)
            if mp3_path:
                await cleanup_temp(mp3_path)

    # --- Self-update ---

    @router.message(Command("update_prox"))
    async def update_prox_command(message: Message) -> None:
        if _update_lock.locked():
            await message.answer("Update already in progress.")
            return

        git_dir = _BOT_REPO_DIR / ".git"
        if not git_dir.exists():
            await message.answer("Not a git repository — cannot update.")
            return

        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "fetch",
                "origin",
                cwd=str(_BOT_REPO_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
        except Exception:
            logger.exception("git_fetch_failed")
            await message.answer("git fetch failed.")
            return

        proc = await asyncio.create_subprocess_exec(
            "git",
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
            cwd=str(_BOT_REPO_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        branch = stdout.decode().strip()

        proc = await asyncio.create_subprocess_exec(
            "git",
            "log",
            f"HEAD..origin/{branch}",
            "--oneline",
            "-20",
            cwd=str(_BOT_REPO_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        changelog = stdout.decode().strip()

        if not changelog:
            await message.answer("Already up to date.")
            return

        await message.answer(
            f"New commits on <b>{branch}</b>:\n\n<code>{changelog}</code>",
            parse_mode="HTML",
            reply_markup=build_update_keyboard(),
        )

    @router.callback_query(F.data == "update:confirm")
    async def update_confirm_callback(callback: CallbackQuery) -> None:
        msg = callback.message
        if not isinstance(msg, Message):
            return
        await callback.answer()

        if _update_lock.locked():
            await msg.edit_text("Update already in progress.")
            return

        async with _update_lock:
            await msg.edit_text("Pulling updates...")

            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                cwd=str(_BOT_REPO_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            branch = stdout.decode().strip()

            proc = await asyncio.create_subprocess_exec(
                "git",
                "pull",
                "origin",
                branch,
                cwd=str(_BOT_REPO_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode().strip()[:MAX_OUTPUT]
                await msg.edit_text(
                    f"git pull failed:\n<code>{err}</code>",
                    parse_mode="HTML",
                )
                return

            await msg.edit_text("Installing dependencies...")

            proc = await asyncio.create_subprocess_exec(
                "uv",
                "sync",
                cwd=str(_BOT_REPO_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode().strip()[:MAX_OUTPUT]
                await msg.edit_text(
                    f"uv sync failed:\n<code>{err}</code>",
                    parse_mode="HTML",
                )
                return

            await msg.edit_text("Update complete. Restarting...")
            await request_restart()

    @router.callback_query(F.data == "update:cancel")
    async def update_cancel_callback(callback: CallbackQuery) -> None:
        msg = callback.message
        if not isinstance(msg, Message):
            return
        await callback.answer()
        await msg.edit_text("Update cancelled.")

    # --- Custom & catch-all ---

    @router.message(F.text.regexp(r"^/(user|project):\w+"))
    async def custom_command_handler(
        message: Message, project: Project, thread_id: int | None
    ) -> None:
        if not message.text:
            return
        parts = message.text.split(maxsplit=1)
        cmd_part = parts[0]  # e.g., /user:foo
        arguments = parts[1] if len(parts) > 1 else ""
        prefix, name = cmd_part[1:].split(":", maxsplit=1)
        scope = "user" if prefix == "user" else "project"
        prompt = services.command_storage.resolve_prompt(name, scope, project.directory, arguments)
        if prompt is None:
            await message.answer(f"Command '/{prefix}:{name}' not found.")
            return
        await _enqueue_prompt(message, prompt, project, services, thread_id)

    @router.message(F.text.regexp(r"^/[a-z][a-z0-9_]*(\s|$)"))
    async def claude_slash_command_handler(
        message: Message, project: Project, thread_id: int | None
    ) -> None:
        if not message.text:
            return
        parts = message.text.strip().split(maxsplit=1)
        word = parts[0][1:]  # strip leading /

        # Skip bot commands and /start
        if word.endswith("_prox") or word == "start":
            return

        # /clear → reset session, then start fresh (no resume)
        if word == "clear":
            if thread_id is not None:
                await services.session_manager.reset_thread_session(message.chat.id, thread_id)
            else:
                await services.session_manager.reset_session(project.id)
            await _enqueue_prompt(message, f"/{word}", project, services, thread_id)
            return

        # All other Claude commands → forward with current session (resume)
        await _enqueue_prompt(message, message.text, project, services, thread_id)

    @router.message(F.text.startswith("!"))
    async def bash_handler(message: Message, project: Project) -> None:
        if not message.text or not message.bot:
            return

        bot = message.bot
        command = message.text[1:].strip()
        if not command:
            await message.answer("Usage: ! <command>\nExample: ! ls -la")
            return

        thread_id = message.message_thread_id
        status = await bot.send_message(
            chat_id=message.chat.id,
            text=f"Running: {command[:100]}...",
            message_thread_id=thread_id,
        )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=project.directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            output = (stdout + stderr).decode("utf-8", errors="ignore").strip() or "(no output)"
            output = output[:MAX_OUTPUT]

            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f"$ {command}\n\n{output}",
            )
        except TimeoutError:
            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f"$ {command}\n\nError: timed out after 30s",
            )
        except Exception as exc:  # noqa: BLE001
            await bot.edit_message_text(
                chat_id=status.chat.id,
                message_id=status.message_id,
                text=f"$ {command}\n\nError: {str(exc)[:MAX_OUTPUT]}",
            )

    @router.message(F.text)
    async def text_handler(message: Message, project: Project, thread_id: int | None) -> None:
        if not message.text:
            return
        await _enqueue_prompt(message, message.text, project, services, thread_id)

    return router


async def _create_project_thread(
    bot: Any,
    chat_id: int,
    project: Project,
    services: Services,
) -> int:
    """Create a forum topic for a project and return the thread ID."""
    thread_count = await services.sessions.count_threads_by_project(project.id)
    topic_name = project.name if thread_count == 0 else f"{project.name} {thread_count + 1}"
    topic = await bot.create_forum_topic(chat_id, name=topic_name)
    db_session = await services.sessions.create(
        {
            "project_id": project.id,
            "status": "active",
            "message_thread_id": topic.message_thread_id,
        }
    )
    meta_text = f"Project: {project.name}\nDir: {project.directory}\nSession: #{db_session.id}"
    meta_msg = await bot.send_message(chat_id, meta_text, message_thread_id=topic.message_thread_id)
    try:
        await bot.pin_chat_message(chat_id, meta_msg.message_id)
    except Exception:  # noqa: BLE001
        pass
    return int(topic.message_thread_id)


async def _enqueue_prompt(
    message: Message,
    text: str,
    project: Project,
    services: Services,
    thread_id: int | None = None,
) -> None:
    chat_id = message.chat.id
    assert message.bot is not None
    bot = message.bot
    task_key = (chat_id, thread_id)
    retry_count = 0

    async def run_query() -> None:
        nonlocal retry_count
        logger.info(
            "processing_message",
            chat_id=chat_id,
            project_id=project.id,
            thread_id=thread_id,
            text=text[:100],
        )

        sender = MessageSender(bot, chat_id, message_thread_id=thread_id)
        status = await bot.send_message(
            chat_id=chat_id, text="Thinking...", message_thread_id=thread_id
        )
        sender.set_initial_message(status.message_id)
        renderer = StreamRenderer(sender)
        permission_handler = get_permission_handler(bot, chat_id, thread_id)

        task = asyncio.current_task()
        if task is not None:
            set_active_task(task_key, task)

        sdk_result_error: str | None = None

        try:
            session = await services.session_manager.get_or_create(
                project.id, thread_id=thread_id, chat_id=chat_id
            )
            if session.resumed:
                await bot.send_message(chat_id, "Session resumed.", message_thread_id=thread_id)
            is_bypass = project.permission_mode == "bypassPermissions"
            mode = _map_permission_mode(project.permission_mode)

            mcp_configs = await services.mcp_configs.find_enabled_by_project(project.id)
            mcp_servers: dict[str, Any] = {}
            for cfg in mcp_configs:
                mcp_servers[cfg.server_name] = json.loads(cfg.config_json)

            permission_hook: PermissionHook | None = None
            if not is_bypass:
                if project.permission_mode == "dontAsk":

                    async def auto_allow(_tool_name: str, _tool_input: dict[str, Any]) -> bool:
                        return True

                    permission_hook = auto_allow
                else:
                    permission_hook = permission_handler.request_permission

            async for sdk_message in iter_claude_query(
                prompt=text,
                cwd=project.directory,
                permission_mode=mode,
                resume_session_id=session.claude_session_id,
                mcp_servers=mcp_servers if mcp_servers else None,
                permission_hook=permission_hook,
                model=session.model or DEFAULT_MODEL,
            ):
                session_id = _extract_session_id(sdk_message)
                if session_id:
                    await services.session_manager.update_claude_session_id(
                        session.db_id, session_id
                    )

                slash_cmds = _extract_slash_commands(sdk_message)
                if slash_cmds is not None:
                    services.claude_slash_commands.update(slash_cmds)

                result_error = _extract_result_error(sdk_message)
                if result_error:
                    sdk_result_error = result_error

                await renderer.process_message(sdk_message)

            await renderer.finish()
        except asyncio.CancelledError:
            await sender.update_text("Cancelled.")
        except Exception as exc:  # noqa: BLE001
            error_text = f"{sdk_result_error or ''} {exc}".lower()
            if _is_rate_limit_error(error_text) and retry_count < _MAX_RATE_LIMIT_RETRIES:
                retry_count += 1
                logger.warning(
                    "rate_limit_hit",
                    error=str(exc),
                    attempt=retry_count,
                    max_retries=_MAX_RATE_LIMIT_RETRIES,
                )
                await sender.update_text(
                    f"Rate limit hit. Retrying in 5 min "
                    f"({retry_count}/{_MAX_RATE_LIMIT_RETRIES})..."
                )

                async def _delayed_retry() -> None:
                    await asyncio.sleep(300)
                    message_queue.enqueue(task_key, run_query)

                asyncio.create_task(_delayed_retry())
            elif _is_rate_limit_error(error_text):
                logger.warning("rate_limit_exhausted", error=str(exc))
                await sender.update_text("Rate limit persists. Please try again later.")
            elif sdk_result_error:
                logger.warning(
                    "claude_query_failed_with_result_error",
                    error=str(exc),
                    sdk_result_error=sdk_result_error,
                )
                await sender.update_text(sdk_result_error)
            else:
                logger.exception("claude_query_failed", error=str(exc))
                await sender.update_text(f"Error: {exc}")
        finally:
            clear_task(task_key)

    message_queue.enqueue(task_key, run_query)


_MAX_RATE_LIMIT_RETRIES = 3
_RATE_LIMIT_KEYWORDS = ("rate limit", "rate_limit", "overloaded", "too many requests", "429")


def _is_rate_limit_error(text: str) -> bool:
    """Check if an error message indicates a rate limit."""
    lower = text.lower()
    return any(kw in lower for kw in _RATE_LIMIT_KEYWORDS)


def _extract_session_id(message: Any) -> str | None:
    try:
        from claude_agent_sdk import ResultMessage, SystemMessage

        if isinstance(message, SystemMessage) and message.subtype == "init":
            data = message.data
            if isinstance(data, dict):
                sid = data.get("session_id")
                if isinstance(sid, str):
                    return sid
        if isinstance(message, ResultMessage):
            sid = message.session_id
            if isinstance(sid, str):
                return sid
    except ImportError:
        pass

    # Fallback: attribute access
    subtype = _field(message, "subtype")
    if subtype == "init":
        data = _field(message, "data")
        if isinstance(data, dict):
            sid = data.get("session_id")
            if isinstance(sid, str):
                return sid
    session_id = _field(message, "session_id")
    if isinstance(session_id, str) and session_id:
        return session_id
    return None


def _extract_slash_commands(message: Any) -> list[str] | None:
    """Extract available slash commands from SDK init message."""
    try:
        from claude_agent_sdk import SystemMessage

        if isinstance(message, SystemMessage) and message.subtype == "init":
            data = message.data
            if isinstance(data, dict):
                cmds = data.get("slash_commands")
                if isinstance(cmds, list):
                    return [c for c in cmds if isinstance(c, str)]
    except ImportError:
        pass

    subtype = _field(message, "subtype")
    if subtype == "init":
        data = _field(message, "data")
        if isinstance(data, dict):
            cmds = data.get("slash_commands")
            if isinstance(cmds, list):
                return [c for c in cmds if isinstance(c, str)]
    return None


def _extract_result_error(message: Any) -> str | None:
    try:
        from claude_agent_sdk import ResultMessage

        if isinstance(message, ResultMessage):
            if message.is_error:
                result = message.result
                if isinstance(result, str) and result.strip():
                    return result.strip()
            return None
    except ImportError:
        pass

    # Fallback
    is_error = _field(message, "is_error")
    if not isinstance(is_error, bool) or not is_error:
        return None
    result = _field(message, "result")
    if isinstance(result, str) and result.strip():
        return result.strip()
    return None


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _map_permission_mode(mode: str) -> str:
    if mode == "dontAsk":
        return "bypassPermissions"
    return mode


def _command_args(message: Message) -> str:
    text = message.text or ""
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def _format_uptime(seconds: float) -> str:
    total = int(seconds)
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)

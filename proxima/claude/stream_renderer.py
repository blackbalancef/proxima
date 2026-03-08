from __future__ import annotations

import asyncio
import time
from typing import Any

from proxima.logging import get_logger
from proxima.telegram.message_sender import MessageSender
from proxima.utils.markdown_to_html import markdown_to_html

logger = get_logger(__name__)

TOOL_ICONS: dict[str, str] = {
    "Read": "[read]",
    "Write": "[write]",
    "Edit": "[edit]",
    "Bash": "[bash]",
    "Glob": "[glob]",
    "Grep": "[grep]",
    "WebSearch": "[web]",
    "WebFetch": "[web]",
    "Task": "[task]",
}

DEBOUNCE_DRAFT_SECONDS = 0.15
DEBOUNCE_EDIT_SECONDS = 1.0
STATS_DISPLAY_SECONDS = 10


class StreamRenderer:
    def __init__(self, sender: MessageSender) -> None:
        self.sender = sender
        self._debounce_interval = (
            DEBOUNCE_DRAFT_SECONDS if sender.is_private else DEBOUNCE_EDIT_SECONDS
        )
        self.accumulated_text = ""
        self._debounce_task: asyncio.Task[None] | None = None
        self.status_message_id: int | None = None
        self._current_status_text: str = ""
        self._has_thinking = False
        self._thinking_buffer = ""
        self._start_time = time.monotonic()

    async def process_message(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("type")

        if msg_type == "result":
            await self._handle_result(msg)
        elif msg_type == "system":
            await self._handle_system(msg)
        elif msg_type == "assistant":
            await self._handle_assistant(msg)
        elif msg_type == "user":
            await self._handle_user(msg)
        elif msg_type == "stream_event":
            await self._handle_stream_event(msg)
        else:
            logger.info("cli_unhandled", msg_type=msg_type)

    async def _handle_result(self, msg: dict[str, Any]) -> None:
        result = msg.get("result")
        is_error = msg.get("is_error", False)
        logger.info(
            "cli_result",
            result_len=len(result) if isinstance(result, str) else 0,
            is_error=is_error,
            num_turns=msg.get("num_turns"),
            duration_ms=msg.get("duration_ms"),
            cost=msg.get("total_cost_usd"),
        )
        if isinstance(result, str):
            self.accumulated_text = result
            await self.flush()
        await self._show_result_stats(msg)

    async def _handle_system(self, msg: dict[str, Any]) -> None:
        subtype = msg.get("subtype")
        logger.info("cli_system", subtype=subtype)
        if subtype == "init":
            data = msg.get("data", {})
            slash_cmds: list[str] = []
            if isinstance(data, dict):
                cmds = data.get("slash_commands")
                if isinstance(cmds, list):
                    slash_cmds = [f"/{c}" for c in cmds if isinstance(c, str)]
            if slash_cmds:
                hint = ", ".join(slash_cmds[:8])
                await self._send_status_persistent(f"Session initialized — {hint}")
            else:
                await self._send_status_persistent("Session initialized")
        elif subtype:
            await self._send_status_persistent(f"[system] {subtype}")

    async def _handle_assistant(self, msg: dict[str, Any]) -> None:
        message = msg.get("message", {})
        content = message.get("content", [])
        is_subagent = msg.get("parent_tool_use_id") is not None

        block_summary = _summarize_blocks(content)
        logger.info(
            "cli_assistant",
            blocks=block_summary,
            model=message.get("model"),
            subagent=is_subagent,
        )

        if is_subagent:
            await self._show_subagent_status(content)
            return

        for block in content:
            block_type = block.get("type") if isinstance(block, dict) else None
            if block_type == "thinking":
                thinking = block.get("thinking", "")
                logger.info(
                    "cli_thinking",
                    thinking_len=len(thinking),
                    preview=thinking[:150].replace("\n", " "),
                )
                await self._handle_thinking(thinking)
            elif block_type == "text":
                text = block.get("text", "")
                logger.info(
                    "cli_text",
                    text_len=len(text),
                    preview=text[:150].replace("\n", " "),
                )
                await self._clear_thinking()
                self.accumulated_text = text
                self._schedule_update()
            elif block_type == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                logger.info(
                    "cli_tool_use",
                    tool=tool_name,
                    input_keys=list(tool_input.keys()) if isinstance(tool_input, dict) else [],
                )
                await self._clear_thinking()
                await self._show_tool_status(tool_name, tool_input)
            elif block_type == "tool_result":
                logger.info("cli_tool_result", tool_use_id=block.get("tool_use_id"))
                await self._complete_tool_status()

    async def _handle_user(self, msg: dict[str, Any]) -> None:
        is_subagent = msg.get("parent_tool_use_id") is not None
        message = msg.get("message", {})
        content = message.get("content", [])
        logger.info(
            "cli_user",
            subagent=is_subagent,
            content_blocks=len(content) if isinstance(content, list) else 0,
        )
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    await self._complete_tool_status()

    async def _handle_stream_event(self, msg: dict[str, Any]) -> None:
        if msg.get("parent_tool_use_id") is not None:
            return

        event = msg.get("event", {})
        event_type = event.get("type")
        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    self.accumulated_text += text
                    self._schedule_update()
            elif delta_type == "thinking_delta":
                thinking_text = delta.get("thinking", "")
                if thinking_text:
                    self._thinking_buffer += thinking_text
                    preview = self._thinking_buffer[:500].replace("\n", " ")
                    if len(self._thinking_buffer) > 500:
                        preview += "..."
                    content = f"Thinking...\n\n<i>{preview}</i>"
                    await self.sender.send_draft(content)
                    self._has_thinking = True
        elif event_type == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "thinking":
                self._thinking_buffer = ""
            elif block.get("type") == "text":
                await self._clear_thinking()
                self.accumulated_text = ""

    async def flush(self) -> None:
        if self._debounce_task:
            self._debounce_task.cancel()
            self._debounce_task = None
        await self._clear_thinking()
        await self._complete_tool_status()
        if self.accumulated_text:
            await self.sender.update_text(markdown_to_html(self.accumulated_text))

    async def finish(self) -> None:
        await self.flush()

    def _schedule_update(self) -> None:
        if self._debounce_task:
            return

        async def debounce() -> None:
            await asyncio.sleep(self._debounce_interval)
            self._debounce_task = None
            html = (
                markdown_to_html(self.accumulated_text)
                if self.accumulated_text
                else "Thinking..."
            )
            await self.sender.send_draft(html)

        self._debounce_task = asyncio.create_task(debounce())

    async def _handle_thinking(self, text: str) -> None:
        preview = text[:500].replace("\n", " ")
        if len(text) > 500:
            preview += "..."
        content = f"Thinking...\n\n<i>{preview}</i>"
        await self.sender.send_draft(content)
        self._has_thinking = True

    async def _clear_thinking(self) -> None:
        self._has_thinking = False

    async def _show_subagent_status(self, content: list[Any]) -> None:
        summary = ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    summary = block.get("text", "")[:80].replace("\n", " ")
                    break
        text = f"[task] Subagent working... {summary}".strip()
        self._current_status_text = text
        try:
            if self.status_message_id:
                await self.sender.edit_status(self.status_message_id, text)
            else:
                self.status_message_id = await self.sender.send_status(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("subagent_status_failed", error=str(exc))

    async def _show_result_stats(self, msg: dict[str, Any]) -> None:
        duration = time.monotonic() - self._start_time
        parts: list[str] = []

        if duration >= 60:
            parts.append(f"{duration / 60:.1f}m")
        else:
            parts.append(f"{duration:.0f}s")

        cost_usd = msg.get("total_cost_usd")
        if isinstance(cost_usd, int | float) and cost_usd > 0:
            parts.append(f"${cost_usd:.4f}")

        num_turns = msg.get("num_turns")
        if isinstance(num_turns, int) and num_turns > 0:
            parts.append(f"{num_turns} turns")

        if parts:
            stats_text = " | ".join(parts)
            await self._send_status_persistent(stats_text)

    async def _send_status_persistent(self, text: str) -> None:
        try:
            await self.sender.send_status(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("status_send_failed", error=str(exc))

    async def _show_tool_status(self, tool_name: str, tool_input: Any) -> None:
        icon = TOOL_ICONS.get(tool_name, "[tool]")
        detail = ""

        if isinstance(tool_input, dict):
            if "file_path" in tool_input:
                detail = f" {tool_input['file_path']}"
            elif "command" in tool_input:
                detail = f" {str(tool_input['command'])[:60]}"
            elif "pattern" in tool_input:
                detail = f" {tool_input['pattern']}"
            elif "query" in tool_input:
                detail = f" {tool_input['query']}"
            elif "prompt" in tool_input:
                detail = f" {str(tool_input['prompt'])[:60]}"

        text = f"{icon} {tool_name}{detail}..."
        self._current_status_text = text
        try:
            if self.status_message_id:
                await self.sender.edit_status(self.status_message_id, text)
            else:
                self.status_message_id = await self.sender.send_status(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("tool_status_failed", error=str(exc))

    async def _complete_tool_status(self) -> None:
        if self.status_message_id:
            try:
                done_text = self._current_status_text.replace("...", " ✓")
                await self.sender.edit_status(self.status_message_id, done_text)
            except Exception as exc:  # noqa: BLE001
                logger.debug("complete_tool_status_failed", error=str(exc))
            self.status_message_id = None
            self._current_status_text = ""


def _summarize_blocks(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            parts.append(type(block).__name__)
            continue
        block_type = block.get("type", "unknown")
        if block_type == "text":
            parts.append(f"Text({len(block.get('text', ''))}ch)")
        elif block_type == "thinking":
            parts.append(f"Thinking({len(block.get('thinking', ''))}ch)")
        elif block_type == "tool_use":
            parts.append(f"Tool({block.get('name', '?')})")
        elif block_type == "tool_result":
            parts.append(f"ToolResult({str(block.get('tool_use_id', ''))[:12]})")
        else:
            parts.append(block_type)
    return ", ".join(parts) if parts else "(empty)"

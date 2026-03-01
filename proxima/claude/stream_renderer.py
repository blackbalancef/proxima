from __future__ import annotations

import asyncio
import time
from typing import Any

from proxima.logging import get_logger
from proxima.telegram.message_sender import MessageSender
from proxima.utils.markdown_to_html import markdown_to_html

logger = get_logger(__name__)

# Import SDK types for isinstance checks
try:
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
    )

    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

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

DEBOUNCE_SECONDS = 0.5
STATS_DISPLAY_SECONDS = 10


class StreamRenderer:
    def __init__(self, sender: MessageSender) -> None:
        self.sender = sender
        self.accumulated_text = ""
        self._debounce_task: asyncio.Task[None] | None = None
        self.status_message_id: int | None = None
        self._has_thinking = False
        self._start_time = time.monotonic()

    async def process_message(self, message: Any) -> None:
        if not _SDK_AVAILABLE:
            await self._process_message_fallback(message)
            return

        # ResultMessage
        if isinstance(message, ResultMessage):
            logger.info(
                "sdk_result",
                result_len=len(message.result) if message.result else 0,
                is_error=message.is_error,
                num_turns=message.num_turns,
                duration_ms=message.duration_ms,
                cost=message.total_cost_usd,
                result_preview=message.result[:200] if message.result else None,
            )
            if isinstance(message.result, str):
                self.accumulated_text = message.result
                await self.flush()
            await self._show_result_stats(message)
            return

        # SystemMessage
        if isinstance(message, SystemMessage):
            logger.info(
                "sdk_system",
                subtype=message.subtype,
                data_keys=list(message.data.keys()) if message.data else [],
            )
            await self._handle_system(message)
            return

        # AssistantMessage
        if isinstance(message, AssistantMessage):
            block_summary = _summarize_blocks(message.content)
            is_subagent = message.parent_tool_use_id is not None
            logger.info(
                "sdk_assistant",
                blocks=block_summary,
                model=message.model,
                subagent=is_subagent,
            )

            if is_subagent:
                await self._show_subagent_status(message.content)
                return

            for block in message.content:
                if isinstance(block, ThinkingBlock):
                    logger.info(
                        "sdk_thinking",
                        thinking_len=len(block.thinking),
                        preview=block.thinking[:150].replace("\n", " "),
                    )
                    await self._handle_thinking(block.thinking)
                elif isinstance(block, TextBlock):
                    logger.info(
                        "sdk_text",
                        text_len=len(block.text),
                        preview=block.text[:150].replace("\n", " "),
                    )
                    await self._clear_thinking()
                    self.accumulated_text = block.text
                    self._schedule_update()
                elif isinstance(block, ToolUseBlock):
                    logger.info(
                        "sdk_tool_use",
                        tool=block.name,
                        input_keys=list(block.input.keys()),
                    )
                    await self._clear_thinking()
                    await self._show_tool_status(block.name, block.input)
                elif isinstance(block, ToolResultBlock):
                    logger.info("sdk_tool_result", tool_use_id=block.tool_use_id)
                    await self._clear_tool_status()
            return

        # UserMessage (tool results from SDK)
        try:
            from claude_agent_sdk import UserMessage

            if isinstance(message, UserMessage):
                is_subagent = message.parent_tool_use_id is not None
                has_tool_result = message.tool_use_result is not None
                content_preview = ""
                if isinstance(message.content, str):
                    content_preview = message.content[:150]
                elif isinstance(message.content, list):
                    content_preview = _summarize_blocks(message.content)
                logger.info(
                    "sdk_user",
                    subagent=is_subagent,
                    has_tool_result=has_tool_result,
                    content_preview=content_preview,
                )
                if has_tool_result:
                    await self._clear_tool_status()
                return
        except ImportError:
            pass

        logger.info(
            "sdk_unhandled",
            msg_class=type(message).__name__,
        )

    async def _process_message_fallback(self, message: Any) -> None:
        """Fallback when SDK types can't be imported."""
        result_text = _field(message, "result")
        if isinstance(result_text, str):
            self.accumulated_text = result_text
            await self.flush()
            return

        content = _field(message, "content")
        if isinstance(content, list):
            for block in content:
                text = _field(block, "text")
                if isinstance(text, str):
                    self.accumulated_text = text
                    self._schedule_update()

    async def flush(self) -> None:
        if self._debounce_task:
            self._debounce_task.cancel()
            self._debounce_task = None
        await self._clear_thinking()
        await self._clear_tool_status()
        if self.accumulated_text:
            await self.sender.update_text(markdown_to_html(self.accumulated_text))

    async def finish(self) -> None:
        await self.flush()

    def _schedule_update(self) -> None:
        if self._debounce_task:
            return

        async def debounce() -> None:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            self._debounce_task = None
            html = (
                markdown_to_html(self.accumulated_text)
                if self.accumulated_text
                else "Thinking..."
            )
            await self.sender.update_text(html)

        self._debounce_task = asyncio.create_task(debounce())

    async def _handle_thinking(self, text: str) -> None:
        preview = text[:500].replace("\n", " ")
        if len(text) > 500:
            preview += "..."
        content = f"Thinking...\n\n<i>{preview}</i>"
        # Update the main message with thinking preview
        await self.sender.update_text(content)
        self._has_thinking = True

    async def _clear_thinking(self) -> None:
        """Reset thinking state. Main message will be overwritten by text."""
        self._has_thinking = False

    async def _handle_system(self, message: Any) -> None:
        subtype = _field(message, "subtype")
        if subtype == "init":
            data = _field(message, "data")
            slash_cmds: list[str] = []
            if isinstance(data, dict):
                cmds = data.get("slash_commands")
                if isinstance(cmds, list):
                    slash_cmds = [f"/{c}" for c in cmds if isinstance(c, str)]
            if slash_cmds:
                hint = ", ".join(slash_cmds[:8])
                await self._show_transient(f"Session initialized — {hint}")
            else:
                await self._show_transient("Session initialized")
        elif subtype:
            await self._show_transient(f"[system] {subtype}")

    async def _show_subagent_status(self, content: Any) -> None:
        summary = ""
        if _SDK_AVAILABLE and isinstance(content, list):
            for block in content:
                if isinstance(block, TextBlock):
                    summary = block.text[:80].replace("\n", " ")
                    break
        text = f"[task] Subagent working... {summary}".strip()
        try:
            if self.status_message_id:
                await self.sender.delete_message(self.status_message_id)
            self.status_message_id = await self.sender.send_status(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("subagent_status_failed", error=str(exc))

    async def _show_result_stats(self, message: Any) -> None:
        duration = time.monotonic() - self._start_time
        parts: list[str] = []

        if duration >= 60:
            parts.append(f"{duration / 60:.1f}m")
        else:
            parts.append(f"{duration:.0f}s")

        cost_usd = _field(message, "total_cost_usd")
        if isinstance(cost_usd, int | float) and cost_usd > 0:
            parts.append(f"${cost_usd:.4f}")

        num_turns = _field(message, "num_turns")
        if isinstance(num_turns, int) and num_turns > 0:
            parts.append(f"{num_turns} turns")

        if parts:
            stats_text = " | ".join(parts)
            await self._show_transient(stats_text, delay=STATS_DISPLAY_SECONDS)

    async def _show_transient(self, text: str, delay: float = 5.0) -> None:
        try:
            msg_id = await self.sender.send_status(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("transient_send_failed", error=str(exc))
            return

        async def _cleanup() -> None:
            await asyncio.sleep(delay)
            await self.sender.delete_message(msg_id)

        asyncio.create_task(_cleanup())

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
        try:
            if self.status_message_id:
                await self.sender.delete_message(self.status_message_id)
            self.status_message_id = await self.sender.send_status(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("tool_status_failed", error=str(exc))

    async def _clear_tool_status(self) -> None:
        if self.status_message_id:
            await self.sender.delete_message(self.status_message_id)
            self.status_message_id = None


def _summarize_blocks(content: list[Any]) -> str:
    """Create a short summary of content blocks for logging."""
    parts: list[str] = []
    for block in content:
        cls = type(block).__name__
        if _SDK_AVAILABLE:
            if isinstance(block, TextBlock):
                parts.append(f"Text({len(block.text)}ch)")
            elif isinstance(block, ThinkingBlock):
                parts.append(f"Thinking({len(block.thinking)}ch)")
            elif isinstance(block, ToolUseBlock):
                parts.append(f"Tool({block.name})")
            elif isinstance(block, ToolResultBlock):
                parts.append(f"ToolResult({block.tool_use_id[:12]})")
            else:
                parts.append(cls)
        else:
            parts.append(cls)
    return ", ".join(parts) if parts else "(empty)"


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)

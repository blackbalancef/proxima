from __future__ import annotations

import time

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.methods import SendMessageDraft
from aiogram.types import Message

from proxima.logging import get_logger
from proxima.utils.markdown_to_html import strip_html_tags

logger = get_logger(__name__)

MAX_MESSAGE_LENGTH = 4000


class MessageSender:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_thread_id: int | None = None,
        chat_type: str = "private",
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.is_private = chat_type == "private"
        self._messages: list[int] = []
        self._last_text = ""
        self._draft_id: int | None = None
        self._draft_failed: bool = False

    def _get_or_create_draft_id(self) -> int:
        if self._draft_id is None:
            self._draft_id = max(1, int(time.monotonic() * 1000) & 0x7FFFFFFF)
        return self._draft_id

    async def send_draft(self, text: str) -> None:
        """Stream partial text to the user during generation.

        Private chats: sendMessageDraft (Bot API 9.5+) with native streaming animation.
        Groups/supergroups: fallback to sendMessage + editMessageText.
        Call update_text() when done to send the final formatted message.
        """
        if not text:
            return

        if self.is_private and not self._draft_failed:
            await self._send_draft_native(text)
        else:
            await self._send_draft_edit_fallback(text)

    async def _send_draft_native(self, text: str) -> None:
        """Private chat: sendMessageDraft with native streaming animation."""
        draft_id = self._get_or_create_draft_id()
        plain = strip_html_tags(text)[:MAX_MESSAGE_LENGTH]
        try:
            await self.bot(
                SendMessageDraft(
                    chat_id=self.chat_id,
                    draft_id=draft_id,
                    text=plain,
                    message_thread_id=self.message_thread_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("send_draft_failed_switching_to_edit", error=str(exc))
            self._draft_failed = True
            await self._send_draft_edit_fallback(text)

    async def _send_draft_edit_fallback(self, text: str) -> None:
        """Group/fallback: send placeholder then editMessageText."""
        plain = strip_html_tags(text)[:MAX_MESSAGE_LENGTH]
        if plain == self._last_text:
            return
        if not self._messages:
            try:
                msg = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=plain,
                    message_thread_id=self.message_thread_id,
                )
                self._messages.append(msg.message_id)
                self._last_text = plain
            except Exception as exc:  # noqa: BLE001
                logger.warning("streaming_placeholder_failed", error=str(exc))
        else:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self._messages[0],
                    text=plain,
                )
                self._last_text = plain
            except Exception as exc:  # noqa: BLE001
                if "message is not modified" not in str(exc):
                    logger.debug("streaming_edit_failed", error=str(exc))

    async def update_text(self, text: str) -> None:
        """Send final formatted message (HTML). Replaces draft/placeholder."""
        # Reset draft — the final sendMessage causes the draft animation to disappear
        self._draft_id = None
        # _last_text tracked plain text during streaming; always send final HTML
        self._last_text = ""

        chunks = split_message(text, MAX_MESSAGE_LENGTH)
        for idx, chunk in enumerate(chunks):
            if idx < len(self._messages):
                await self._edit_existing(self._messages[idx], chunk)
            else:
                message = await self._send_new(chunk)
                self._messages.append(message.message_id)

    async def edit_status(self, message_id: int, text: str) -> None:
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id, message_id=message_id, text=text
            )
        except Exception as exc:  # noqa: BLE001
            if "message is not modified" not in str(exc):
                raise

    async def send_status(self, text: str) -> int:
        message = await self.bot.send_message(
            chat_id=self.chat_id, text=text, message_thread_id=self.message_thread_id
        )
        return message.message_id

    async def delete_message(self, message_id: int) -> None:
        try:
            await self.bot.delete_message(chat_id=self.chat_id, message_id=message_id)
        except Exception:  # noqa: BLE001
            return

    async def _edit_existing(self, message_id: int, chunk: str) -> None:
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=message_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:  # noqa: BLE001
            description = str(exc)
            if "message is not modified" in description:
                return
            if "can't parse entities" in description:
                logger.warning("html_parse_failed_fallback_plain_text")
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=message_id,
                    text=strip_html_tags(chunk),
                )
                return
            raise

    async def _send_new(self, chunk: str) -> Message:
        try:
            return await self.bot.send_message(
                chat_id=self.chat_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                message_thread_id=self.message_thread_id,
            )
        except Exception as exc:  # noqa: BLE001
            if "can't parse entities" in str(exc):
                logger.warning("html_parse_failed_fallback_plain_text")
                return await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=strip_html_tags(chunk),
                    message_thread_id=self.message_thread_id,
                )
            raise


def split_message(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        split_index = remaining.rfind("\n", 0, max_len)
        if split_index < max_len // 2:
            split_index = remaining.rfind(" ", 0, max_len)
        if split_index < max_len // 2:
            split_index = max_len

        chunks.append(remaining[:split_index])
        remaining = remaining[split_index:].lstrip()

    return chunks

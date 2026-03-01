from __future__ import annotations

from dataclasses import dataclass

import pytest

from proxima.telegram.message_sender import MessageSender


@dataclass
class SentMessage:
    message_id: int


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[tuple[int, int, str]] = []
        self.messages: list[tuple[int, str]] = []
        self.deleted: list[int] = []

    async def edit_message_text(self, chat_id: int, message_id: int, text: str, **kwargs):  # type: ignore[no-untyped-def]
        self.edits.append((chat_id, message_id, text))
        return True

    async def send_message(self, chat_id: int, text: str, **kwargs):  # type: ignore[no-untyped-def]
        self.messages.append((chat_id, text))
        return SentMessage(message_id=100 + len(self.messages))

    async def delete_message(self, chat_id: int, message_id: int):  # type: ignore[no-untyped-def]
        self.deleted.append(message_id)
        return True


@pytest.mark.asyncio
async def test_sender_edits_initial_message() -> None:
    bot = FakeBot()
    sender = MessageSender(bot, 123)  # type: ignore[arg-type]
    sender.set_initial_message(10)

    await sender.update_text("hello")

    assert bot.edits == [(123, 10, "hello")]


@pytest.mark.asyncio
async def test_sender_splits_long_messages() -> None:
    bot = FakeBot()
    sender = MessageSender(bot, 123)  # type: ignore[arg-type]
    sender.set_initial_message(10)

    await sender.update_text("a" * 4500)

    assert len(bot.edits) == 1
    assert len(bot.messages) == 1

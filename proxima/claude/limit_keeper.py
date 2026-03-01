from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from proxima.logging import get_logger

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)

DEFAULT_WINDOW_SECONDS = 18000
ERROR_RETRY_SECONDS = 300
BUFFER_SECONDS = 60


class LimitKeeper:
    def __init__(
        self,
        api_key: str,
        bot: Bot,
        notify_chat_ids: list[int],
        model: str,
    ) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._bot = bot
        self._notify_chat_ids = notify_chat_ids
        self._model = model
        self._task: asyncio.Task[None] | None = None
        self._last_user_activity: datetime | None = None
        self._last_ping_time: datetime | None = None
        self._window_seconds: float = DEFAULT_WINDOW_SECONDS

    def touch(self) -> None:
        """Called from router on every user request."""
        self._last_user_activity = datetime.now(UTC)

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("limit_keeper_started", model=self._model)

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("limit_keeper_stopped")

    async def _loop(self) -> None:
        while True:
            try:
                info = await self._ping()
                self._last_ping_time = datetime.now(UTC)

                await self._notify(info)

                delay = info.tokens_reset_seconds + BUFFER_SECONDS
                if delay > 0:
                    await asyncio.sleep(delay)

                # If user activity happened after last ping,
                # wait for the remaining window before pinging again
                while True:
                    if self._last_user_activity is None:
                        break
                    if self._last_ping_time is None:
                        break
                    if self._last_user_activity <= self._last_ping_time:
                        break

                    elapsed = (
                        datetime.now(UTC) - self._last_user_activity
                    ).total_seconds()
                    remaining = self._window_seconds - elapsed + BUFFER_SECONDS
                    if remaining <= 0:
                        break

                    logger.debug(
                        "limit_keeper_skip_ping",
                        reason="user_activity",
                        sleep_seconds=remaining,
                    )
                    await asyncio.sleep(remaining)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                import anthropic

                if isinstance(exc, anthropic.BadRequestError):
                    logger.warning(
                        "limit_keeper_stopped_non_retryable", error=str(exc),
                    )
                    return
                logger.exception("limit_keeper_error")
                await asyncio.sleep(ERROR_RETRY_SECONDS)

    async def _ping(self) -> _LimitInfo:
        logger.debug("limit_keeper_pinging", model=self._model)
        resp = await self._client.messages.with_raw_response.create(
            model=self._model,
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        headers = resp.headers
        info = _parse_headers(headers)

        if info.tokens_reset_seconds > 0:
            self._window_seconds = info.tokens_reset_seconds

        logger.info(
            "limit_keeper_ping_ok",
            tokens_remaining=info.tokens_remaining,
            tokens_reset_seconds=info.tokens_reset_seconds,
            requests_remaining=info.requests_remaining,
            requests_reset_seconds=info.requests_reset_seconds,
        )

        return info

    async def _notify(self, info: _LimitInfo) -> None:
        now = datetime.now(UTC)
        tokens_reset_time = now + _timedelta_seconds(info.tokens_reset_seconds)
        requests_reset_time = now + _timedelta_seconds(info.requests_reset_seconds)

        text = (
            f"\U0001f504 Limits refreshed\n"
            f"Tokens remaining: {info.tokens_remaining:,}"
            f" | Reset: {tokens_reset_time:%H:%M} UTC\n"
            f"Requests remaining: {info.requests_remaining:,}"
            f" | Reset: {requests_reset_time:%H:%M} UTC"
        )

        for chat_id in self._notify_chat_ids:
            try:
                await self._bot.send_message(chat_id, text)
            except Exception:
                logger.exception("limit_keeper_notify_failed", chat_id=chat_id)


class _LimitInfo:
    __slots__ = (
        "tokens_remaining",
        "tokens_reset_seconds",
        "requests_remaining",
        "requests_reset_seconds",
    )

    def __init__(
        self,
        tokens_remaining: int,
        tokens_reset_seconds: float,
        requests_remaining: int,
        requests_reset_seconds: float,
    ) -> None:
        self.tokens_remaining = tokens_remaining
        self.tokens_reset_seconds = tokens_reset_seconds
        self.requests_remaining = requests_remaining
        self.requests_reset_seconds = requests_reset_seconds


def _parse_reset_value(value: str) -> float:
    """Parse anthropic reset header value to seconds.

    The header can be an ISO-8601 timestamp (e.g. '2024-01-01T12:00:00Z')
    or a duration string like '5h30m' / '30s'.
    """
    value = value.strip()
    if not value:
        return 0.0

    # ISO-8601 timestamp
    if "T" in value or "-" in value:
        try:
            reset_dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            diff = (reset_dt - datetime.now(UTC)).total_seconds()
            return max(0.0, diff)
        except ValueError:
            pass

    # Duration string: 5h30m10s
    total = 0.0
    current = ""
    for ch in value:
        if ch.isdigit() or ch == ".":
            current += ch
        elif ch in ("h", "m", "s"):
            if not current:
                continue
            num = float(current)
            if ch == "h":
                total += num * 3600
            elif ch == "m":
                total += num * 60
            else:
                total += num
            current = ""

    return total


def _parse_headers(headers: object) -> _LimitInfo:
    """Extract rate-limit info from Anthropic response headers."""

    def _get(name: str, default: str = "0") -> str:
        if hasattr(headers, "get"):
            return headers.get(name, default)  # type: ignore[no-any-return]
        return default

    tokens_remaining = int(_get("anthropic-ratelimit-tokens-remaining", "0"))
    tokens_reset = _parse_reset_value(
        _get("anthropic-ratelimit-tokens-reset", "")
    )
    requests_remaining = int(_get("anthropic-ratelimit-requests-remaining", "0"))
    requests_reset = _parse_reset_value(
        _get("anthropic-ratelimit-requests-reset", "")
    )

    return _LimitInfo(
        tokens_remaining=tokens_remaining,
        tokens_reset_seconds=tokens_reset,
        requests_remaining=requests_remaining,
        requests_reset_seconds=requests_reset,
    )


def _timedelta_seconds(seconds: float) -> timedelta:
    return timedelta(seconds=seconds)

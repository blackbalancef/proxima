from __future__ import annotations

import pytest

from proxima.bot.router import _is_rate_limit_error


class TestIsRateLimitError:
    @pytest.mark.parametrize(
        "text",
        [
            "rate limit exceeded",
            "Rate Limit Exceeded",
            "rate_limit_error",
            "overloaded",
            "Overloaded: try again later",
            "too many requests",
            "HTTP 429: Too Many Requests",
            "Error code: 429",
            "anthropic rate_limit reached",
        ],
    )
    def test_detects_rate_limit(self, text: str) -> None:
        assert _is_rate_limit_error(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "invalid api key",
            "connection timeout",
            "internal server error",
            "model not found",
            "",
            "something went wrong",
        ],
    )
    def test_ignores_non_rate_limit(self, text: str) -> None:
        assert _is_rate_limit_error(text) is False

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from proxima.lifecycle import (
    request_restart,
    reset_restart,
    should_restart,
)
from proxima.telegram.keyboards import build_update_keyboard


def test_should_restart_default_false() -> None:
    reset_restart()
    assert should_restart() is False


@pytest.mark.asyncio
async def test_request_restart_sets_flag() -> None:
    reset_restart()
    import proxima.lifecycle as lc

    cb = AsyncMock()
    lc._shutdown_callback = cb

    await request_restart()

    assert should_restart() is True
    cb.assert_awaited_once()
    reset_restart()
    lc._shutdown_callback = None


def test_reset_restart_clears_flag() -> None:
    import proxima.lifecycle as lc

    lc._restart_requested = True
    assert should_restart() is True
    reset_restart()
    assert should_restart() is False


def test_build_update_keyboard() -> None:
    kb = build_update_keyboard()
    rows = kb.inline_keyboard
    assert len(rows) == 1
    assert len(rows[0]) == 2
    assert rows[0][0].callback_data == "update:confirm"
    assert rows[0][1].callback_data == "update:cancel"

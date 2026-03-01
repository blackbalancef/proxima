from proxima.cli.tool import _find_running_bot_pids


def test_find_running_bot_pids_returns_list() -> None:
    # Smoke test: should return a list (likely empty in test env)
    result = _find_running_bot_pids()
    assert isinstance(result, list)

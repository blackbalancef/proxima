from proxima.claude.query_runner import cancel_query, clear_task, set_active_task


class DummyTask:
    def __init__(self) -> None:
        self._done = False
        self.cancelled = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> bool:
        self.cancelled = True
        self._done = True
        return True


def test_cancel_query_returns_false_if_missing() -> None:
    clear_task(999)
    assert cancel_query(999) is False


def test_set_active_task_and_cancel() -> None:
    task = DummyTask()
    set_active_task(1, task)  # type: ignore[arg-type]

    assert cancel_query(1) is True
    assert task.cancelled is True
    assert cancel_query(1) is False

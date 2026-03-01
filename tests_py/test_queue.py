import asyncio

import pytest

from proxima.utils.queue import SequentialQueue


@pytest.mark.asyncio
async def test_sequential_same_key() -> None:
    queue = SequentialQueue()
    result: list[int] = []

    async def first() -> None:
        await asyncio.sleep(0.05)
        result.append(1)

    async def second() -> None:
        result.append(2)

    queue.enqueue(1, first)
    queue.enqueue(1, second)

    await asyncio.sleep(0.2)
    assert result == [1, 2]


@pytest.mark.asyncio
async def test_concurrent_different_keys() -> None:
    queue = SequentialQueue()
    result: list[str] = []

    async def first() -> None:
        await asyncio.sleep(0.05)
        result.append("a")

    async def second() -> None:
        result.append("b")

    queue.enqueue(1, first)
    queue.enqueue(2, second)

    await asyncio.sleep(0.2)
    assert result == ["b", "a"]

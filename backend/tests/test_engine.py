import asyncio
import pytest
from app.engine import BatchRunner, EventBus


async def drain(q: asyncio.Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


async def test_batch_runs_all_items():
    bus = EventBus()
    q = bus.subscribe("p1")
    done: list[int] = []
    async def worker(n: int):
        await asyncio.sleep(0.01)
        done.append(n)
    runner = BatchRunner(concurrency=2, bus=bus)
    await runner.start("p1", [1, 2, 3], worker)
    assert runner.is_running("p1")
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    assert sorted(done) == [1, 2, 3]
    events = await drain(q)
    assert {"type": "batch_done"} in events
    assert sum(1 for e in events if e["type"] == "item_done") == 3


async def test_concurrency_limit():
    bus = EventBus()
    active = {"now": 0, "max": 0}
    async def worker(n: int):
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        await asyncio.sleep(0.03)
        active["now"] -= 1
    runner = BatchRunner(concurrency=2, bus=bus)
    await runner.start("p1", list(range(6)), worker)
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    assert active["max"] <= 2


async def test_reject_double_start():
    bus = EventBus()
    async def worker(n: int):
        await asyncio.sleep(0.05)
    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2], worker)
    with pytest.raises(RuntimeError):
        await runner.start("p1", [3], worker)
    runner.cancel("p1")


async def test_cancel_stops_pending():
    bus = EventBus()
    done: list[int] = []
    async def worker(n: int):
        await asyncio.sleep(0.05)
        done.append(n)
    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2, 3, 4], worker)
    await asyncio.sleep(0.07)   # 让第 1 项完成
    runner.cancel("p1")
    await asyncio.sleep(0.05)
    assert not runner.is_running("p1")
    assert len(done) < 4


async def test_worker_exception_does_not_stop_batch():
    bus = EventBus()
    done: list[int] = []
    async def worker(n: int):
        if n == 2:
            raise RuntimeError("unexpected")
        done.append(n)
    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2, 3], worker)
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    assert done == [1, 3]

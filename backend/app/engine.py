import asyncio
from typing import Awaitable, Callable


class EventBus:
    """按项目 ID 广播事件，供 SSE 订阅。"""

    def __init__(self):
        self._subs: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, pid: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(pid, []).append(q)
        return q

    def unsubscribe(self, pid: str, q: asyncio.Queue) -> None:
        if pid in self._subs and q in self._subs[pid]:
            self._subs[pid].remove(q)

    def publish(self, pid: str, event: dict) -> None:
        for q in self._subs.get(pid, []):
            q.put_nowait(event)


class BatchRunner:
    """带并发上限的批处理。每项目同时只允许一个批次。"""

    def __init__(self, concurrency: int, bus: EventBus):
        self.concurrency = concurrency
        self.bus = bus
        self._batches: dict[str, asyncio.Task] = {}

    def is_running(self, pid: str) -> bool:
        t = self._batches.get(pid)
        return t is not None and not t.done()

    async def start(self, pid: str, items: list[int],
                    worker: Callable[[int], Awaitable[None]],
                    concurrency: int | None = None) -> None:
        if self.is_running(pid):
            raise RuntimeError(f"项目 {pid} 已有任务在运行")
        self._batches[pid] = asyncio.create_task(
            self._run(pid, items, worker, concurrency or self.concurrency))

    def cancel(self, pid: str) -> None:
        t = self._batches.get(pid)
        if t and not t.done():
            t.cancel()

    async def _run(self, pid: str, items: list[int],
                   worker: Callable[[int], Awaitable[None]],
                   concurrency: int) -> None:
        sem = asyncio.Semaphore(concurrency)

        async def one(n: int) -> None:
            async with sem:
                event = {"type": "item_done", "item": n, "ok": True}
                try:
                    await worker(n)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 - 单项意外失败不影响批次
                    event.update(ok=False, error=str(e))
                self.bus.publish(pid, event)

        try:
            await asyncio.gather(*(one(n) for n in items))
        finally:
            self.bus.publish(pid, {"type": "batch_done"})

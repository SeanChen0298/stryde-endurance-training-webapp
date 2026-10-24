"""
Run follow-up work for a request (Garmin backfill, plan generation).

On a long-lived server the work runs as a background task and the request
returns straight away. On Vercel the function is frozen once the response is
sent, so the work runs inline and the request waits for it.
"""
import asyncio
from collections.abc import Coroutine

from config import settings

# Keep references so running tasks aren't garbage-collected
_tasks: set[asyncio.Task] = set()


async def run_after_response(coro: Coroutine) -> None:
    if settings.VERCEL:
        await coro
        return
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

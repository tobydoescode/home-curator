from collections.abc import Awaitable, Callable
from pathlib import Path

from watchfiles import awatch


async def watch_policies(path: Path, on_change: Callable[[], Awaitable[None]]) -> None:
    async for _ in awatch(path.parent):
        try:
            await on_change()
        except Exception:
            # Errors during reload are swallowed; on_change handles them.
            pass

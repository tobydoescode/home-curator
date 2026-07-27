from collections.abc import Awaitable, Callable
from pathlib import Path

from watchfiles import awatch


async def watch_policies(path: Path, on_change: Callable[[], Awaitable[None]]) -> None:
    """Reload when `path` changes.

    The parent directory is watched rather than the file itself, because an
    atomic save replaces the inode: a watch on the file would follow the old
    one and go deaf after the first save. Batches are therefore filtered down
    to the file we actually care about.

    Without that filter every save triggers two reloads — the temporary file
    appearing and the rename — and any unrelated file in the config
    directory, an editor swapfile included, triggers a pointless recompile.
    """
    target = str(path)
    async for batch in awatch(path.parent):
        if not any(str(changed) == target for _, changed in batch):
            continue
        try:
            await on_change()
        except Exception:
            # Errors during reload are swallowed; on_change handles them.
            pass

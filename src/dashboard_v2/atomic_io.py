"""Atomic JSON replacement with bounded retries for Windows sharing conflicts."""
import json
from pathlib import Path
import tempfile
import time


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Every writer owns its staging file; never truncate another writer's data.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name+'.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
        # The handle must be closed before rename on Windows. Brief readers or
        # scanners can still hold the destination without FILE_SHARE_DELETE.
        for attempt in range(8):
            try:
                temporary.replace(path)
                return
            except OSError as exc:
                if getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 7:
                    raise
                time.sleep(min(.02 * (2 ** attempt), .1))
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Do not hide the original write/replace error during cleanup.
                pass

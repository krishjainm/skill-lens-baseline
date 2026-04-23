"""Small filesystem helpers (no third-party imports)."""
from __future__ import annotations

import os


def try_remove_file(path: str) -> None:
    """Delete a file if it exists; ignore errors (best-effort cleanup)."""
    if not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError:
        pass

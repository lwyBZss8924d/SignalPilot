"""Shared multiprocessing context helper for kernel and queue managers.

Uses ``forkserver`` on Linux for faster subprocess startup (the forkserver
process inherits pre-loaded heavy modules via copy-on-write), and falls
back to ``spawn`` everywhere else (macOS, Windows).

Forkserver configuration is **lazy** — ``set_forkserver_preload`` is called
on first use of ``get_mp_context()``, not at import time. This avoids
triggering forkserver initialization from background threads (which
deadlocks in Docker).
"""

from __future__ import annotations

import sys
import threading
from multiprocessing import get_context
from multiprocessing.context import BaseContext

_configured = False
_lock = threading.Lock()

_PRELOAD_MODULES = [
    "signalpilot._runtime.runtime",
    "signalpilot._messaging.notification",
    "signalpilot._ast.compiler",
]


def configure_forkserver() -> None:
    """Configure the forkserver preload list (Linux only). Idempotent."""
    global _configured
    if _configured:
        return
    with _lock:
        if _configured:
            return
        if sys.platform == "linux":
            from multiprocessing import set_forkserver_preload
            set_forkserver_preload(_PRELOAD_MODULES)
        _configured = True


def get_mp_context() -> BaseContext:
    """Return the preferred multiprocessing context for the current platform.

    Linux  -> ``forkserver`` (fast, pre-loaded modules via COW)
    Others -> ``spawn``      (safe default)

    Lazily configures forkserver preload on first call.
    """
    configure_forkserver()
    if sys.platform == "linux":
        return get_context("forkserver")
    return get_context("spawn")

"""Single-slot registry for the currently running long subprocess.

The work queue is a serial single worker, so at most one long inference /
separation subprocess exists at a time. Engines run their subprocess through
`SLOT.run(...)` so `cancel_work` can terminate it from another thread.
"""

from __future__ import annotations

import subprocess
import threading
from types import SimpleNamespace
from typing import Any


class ProcSlot:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    def run(self, command: list[str], **popen_kwargs: Any) -> SimpleNamespace:
        """Popen + wait, registering the process so it can be cancelled."""
        proc = subprocess.Popen(command, **popen_kwargs)
        with self._lock:
            self._proc = proc
        try:
            stdout, stderr = proc.communicate()
        finally:
            with self._lock:
                self._proc = None
        return SimpleNamespace(returncode=proc.returncode, stdout=stdout, stderr=stderr)

    def cancel(self) -> bool:
        """Terminate the currently registered process. Returns True if one was found."""
        with self._lock:
            proc = self._proc
        if proc is None or proc.poll() is not None:
            return False
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return True


SLOT = ProcSlot()

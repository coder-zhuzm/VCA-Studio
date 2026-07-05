"""Small thread-safe JSON storage."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: Path, default: Any) -> None:
        self._path = path
        self._default = default
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write(default)

    def read(self) -> Any:
        with self._lock:
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return self._default

    def write(self, data: Any) -> None:
        with self._lock:
            self._write(data)

    def _write(self, data: Any) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path, {})
        self._lock = threading.RLock()

    def all(self) -> dict[str, Any]:
        data = self._store.read()
        return data if isinstance(data, dict) else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.all().get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            data = self.all()
            data[key] = value
            self._store.write(data)

    def update(self, values: dict[str, Any]) -> None:
        with self._lock:
            data = self.all()
            data.update(values)
            self._store.write(data)

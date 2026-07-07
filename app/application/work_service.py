"""Work metadata creation and lookup service."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .stem_preparer import StemPreparer
    from app.infrastructure.storage import ListRepository
except ModuleNotFoundError:
    from application.stem_preparer import StemPreparer
    from infrastructure.storage import ListRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkService:
    def __init__(self, repo: ListRepository, stem_preparer: StemPreparer) -> None:
        self._repo = repo
        self._stem_preparer = stem_preparer

    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload or {}
        prepared = self._stem_preparer.prepare(payload)
        if not prepared.get("ok"):
            return {"ok": False, "error": str(prepared.get("error") or "输入准备失败。")}

        created_at = _now()
        record = {
            "id": str(prepared["work_id"]),
            "name": str(payload.get("name") or "").strip() or "Untitled Work",
            "input_mode": str(prepared["mode"]),
            "input_files": self._input_files(prepared.get("files") or {}, payload),
            "status": "pending",
            "stage": "prepared",
            "logs": [
                {
                    "level": "info",
                    "message": "Input prepared",
                    "created_at": created_at,
                }
            ],
            "created_at": created_at,
            "updated_at": created_at,
        }

        try:
            self._repo.add(record)
        except OSError as exc:
            self._cleanup_work_dir(record)
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "work": record}

    def list_works(self) -> dict[str, Any]:
        return {"ok": True, "works": self._repo.all()}

    def get_work(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        return {"ok": True, "work": work}

    def _input_files(self, files: dict[str, str], payload: dict[str, Any]) -> list[dict[str, str]]:
        sources = {
            "input_song": str(payload.get("song_path") or "").strip(),
            "vocals": str(payload.get("vocals_path") or "").strip(),
            "instrumental": str(payload.get("instrumental_path") or "").strip(),
        }
        result: list[dict[str, str]] = []
        for role, stored_path in files.items():
            result.append(
                {
                    "role": role,
                    "source_path": sources.get(role, ""),
                    "stored_path": str(stored_path),
                    "filename": Path(str(stored_path)).name,
                }
            )
        return result

    def _cleanup_work_dir(self, record: dict[str, Any]) -> None:
        files = record.get("input_files") or []
        first = next((item.get("stored_path") for item in files if item.get("stored_path")), "")
        if first:
            shutil.rmtree(Path(str(first)).parent.parent, ignore_errors=True)

"""Work metadata creation and lookup service."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.stem_preparer import StemPreparer
from infrastructure.storage import ListRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkService:
    def __init__(self, repo: ListRepository, stem_preparer: StemPreparer) -> None:
        self._repo = repo
        self._stem_preparer = stem_preparer

    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效的创建参数。"}
        prepared = self._stem_preparer.prepare(payload)
        if not prepared.get("ok"):
            return {"ok": False, "error": str(prepared.get("error") or "输入准备失败。")}

        created_at = _now()
        input_files = self._input_files(prepared.get("files") or {}, payload)
        work_dir = self._work_dir_from_input_files(input_files)
        log_entry = {
            "level": "info",
            "message": "Input prepared",
            "created_at": created_at,
        }
        record = {
            "id": str(prepared["work_id"]),
            "name": str(payload.get("name") or "").strip() or "Untitled Work",
            "model_id": str(payload.get("model_id") or "").strip(),
            "input_mode": str(prepared["mode"]),
            "input_files": input_files,
            "status": "pending",
            "stage": "prepared",
            "logs": [log_entry],
            "work_dir": str(work_dir) if work_dir else "",
            "log_path": str(work_dir / "run.log") if work_dir else "",
            "created_at": created_at,
            "updated_at": created_at,
        }

        try:
            self._write_log(record, log_entry)
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

    def delete_work(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        self._cleanup_work_dir(work)
        self._repo.remove(str(work_id))
        return {"ok": True, "works": self._repo.all()}

    def read_work_log(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        log_path = str(work.get("log_path") or "").strip()
        if not log_path:
            return {"ok": False, "error": "Work log not found"}
        path = Path(log_path)
        if not path.is_file():
            return {"ok": False, "error": "Work log not found"}
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "work_id": str(work_id), "log_path": log_path, "content": content}

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

    def _write_log(self, record: dict[str, Any], log_entry: dict[str, str]) -> None:
        log_path = str(record.get("log_path") or "")
        if not log_path:
            return
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"{log_entry['created_at']} [{log_entry['level']}] {log_entry['message']}\n",
            encoding="utf-8",
        )

    def _cleanup_work_dir(self, record: dict[str, Any]) -> None:
        work_dir = self._work_dir_from_record(record)
        if work_dir and self._is_safe_work_dir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

    def _work_dir_from_record(self, record: dict[str, Any]) -> Path | None:
        work_dir = str(record.get("work_dir") or "").strip()
        if work_dir:
            return Path(work_dir)
        return self._work_dir_from_input_files(record.get("input_files") or [])

    def _work_dir_from_input_files(self, files: list[dict[str, Any]]) -> Path | None:
        first = next((item.get("stored_path") for item in files if item.get("stored_path")), "")
        if not first:
            return None
        return Path(str(first)).parent.parent

    def _is_safe_work_dir(self, work_dir: Path) -> bool:
        root = getattr(self._stem_preparer, "_works_dir", None)
        if root is None:
            return work_dir.name.startswith("work_")
        try:
            resolved = work_dir.resolve()
            works_root = Path(root).resolve()
        except OSError:
            return False
        return resolved.name.startswith("work_") and resolved.is_relative_to(works_root)

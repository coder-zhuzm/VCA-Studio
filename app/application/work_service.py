"""Work metadata creation and lookup service."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from application.runtime_service import RuntimeService
from application.stem_preparer import StemPreparer
from infrastructure.storage import ListRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _params(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    f0_method = str(params.get("f0_method") or "rmvpe").strip()
    if f0_method not in {"rmvpe", "harvest", "crepe"}:
        f0_method = "rmvpe"
    device = str(params.get("device") or "auto").strip()
    if device not in {"auto", "cpu", "cuda", "mps"}:
        device = "auto"
    try:
        transpose = int(params.get("transpose") or 0)
    except (TypeError, ValueError):
        transpose = 0

    def number(key: str, default: float) -> float:
        try:
            return float(params.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "transpose": transpose,
        "f0_method": f0_method,
        "index_rate": number("index_rate", 0.75),
        "rms_mix_rate": number("rms_mix_rate", 1),
        "protect": number("protect", 0.33),
        "filter_radius": int(number("filter_radius", 3)),
        "device": device,
    }


class WorkService:
    def __init__(
        self,
        repo: ListRepository,
        stem_preparer: StemPreparer,
        model_repo: ListRepository | None = None,
        runtime: RuntimeService | None = None,
    ) -> None:
        self._repo = repo
        self._stem_preparer = stem_preparer
        self._model_repo = model_repo
        self._runtime = runtime

    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效的创建参数。"}
        model_id = str(payload.get("model_id") or "").strip()
        if not model_id:
            return {"ok": False, "error": "缺少目标模型。"}
        if self._model_repo and not self._model_repo.get(model_id):
            return {"ok": False, "error": "目标模型不存在。"}
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
            "params": _params(payload),
            "input_mode": str(prepared["mode"]),
            "input_files": input_files,
            "status": "pending",
            "stage": "prepared",
            "progress": 10,
            "steps": [self._step("prepare", "done", created_at, "Input prepared")],
            "logs": [log_entry],
            "work_dir": str(work_dir) if work_dir else "",
            "log_path": str(work_dir / "run.log") if work_dir else "",
            "created_at": created_at,
            "updated_at": created_at,
        }

        try:
            self._append_log(record, log_entry)
            self._write_metadata(record)
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

    def start_work(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        if work.get("status") != "pending" or work.get("stage") != "prepared":
            return {"ok": True, "work": work}

        error = self._start_blocker(work)
        if error:
            return {"ok": True, "work": self._fail_work(work, error)}

        return {"ok": True, "work": self._fail_work(work, "真实 RVC 推理尚未接入。")}

    def retry_work(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        if work.get("status") != "failed":
            return {"ok": True, "work": work}
        entry = {"level": "info", "message": "Work reset for retry", "created_at": _now()}
        updated = {
            **work,
            "status": "pending",
            "stage": "prepared",
            "progress": 10,
            "steps": self._reset_steps(work.get("steps") or [], entry),
            "logs": [*(work.get("logs") or []), entry],
            "updated_at": entry["created_at"],
        }
        self._append_log(updated, entry)
        self._write_metadata(updated)
        self._repo.update_item(str(updated["id"]), updated)
        return {"ok": True, "work": updated}

    def rename_work(self, work_id: str, name: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        cleaned = str(name or "").strip()
        if not cleaned:
            return {"ok": False, "error": "作品名称不能为空。"}
        updated = {**work, "name": cleaned, "updated_at": _now()}
        self._write_metadata(updated)
        self._repo.update_item(str(work_id), updated)
        return {"ok": True, "work": updated}

    def export_work(self, work_id: str, target_dir: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        source = self._output_path(work)
        if not source:
            return {"ok": False, "error": "作品还没有可导出的输出文件。"}
        target_root = Path(str(target_dir or "")).expanduser()
        if not target_root.is_dir():
            return {"ok": False, "error": "导出目录不存在。"}
        target = target_root / source.name
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(target)}

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

    def open_work_dir(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        work_dir = self._work_dir_from_record(work)
        if not work_dir or not work_dir.is_dir():
            return {"ok": False, "error": "Work directory not found"}
        return self.open_path(work_dir)

    def open_work_log(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        path = Path(str(work.get("log_path") or ""))
        if not path.is_file():
            return {"ok": False, "error": "Work log not found"}
        return self.open_path(path)

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

    def _start_blocker(self, work: dict[str, Any]) -> str:
        model = self._model_repo.get(str(work.get("model_id") or "")) if self._model_repo else None
        if not model:
            return "目标模型不存在。"
        if model.get("framework") != "rvc":
            return "P0 当前只支持 RVC 推理。"
        checkpoint = str((model.get("files") or {}).get("checkpoint") or "")
        if not checkpoint or not Path(checkpoint).is_file():
            return "RVC 主模型文件缺失。"
        if work.get("input_mode") == "song":
            return "完整歌曲输入还未接入 UVR 分离，请先使用已分离人声。"
        vocals = next((item for item in work.get("input_files") or [] if item.get("role") == "vocals"), None)
        vocals_path = str((vocals or {}).get("stored_path") or "")
        if not vocals_path or not Path(vocals_path).is_file():
            return "人声输入文件缺失。"
        if self._runtime:
            rvc = self._runtime.check_component("rvc")
            if rvc.get("status") != "ready":
                return f"RVC runtime 未就绪：{rvc.get('message') or '未配置'}"
        return ""

    def _fail_work(self, work: dict[str, Any], message: str) -> dict[str, Any]:
        entry = {"level": "error", "message": message, "created_at": _now()}
        updated = {
            **work,
            "status": "failed",
            "stage": "failed",
            "progress": int(work.get("progress") or 0),
            "steps": self._fail_steps(work.get("steps") or [], entry),
            "logs": [*(work.get("logs") or []), entry],
            "updated_at": entry["created_at"],
        }
        self._append_log(updated, entry)
        self._write_metadata(updated)
        self._repo.update_item(str(updated["id"]), updated)
        return updated

    def _append_log(self, record: dict[str, Any], log_entry: dict[str, str]) -> None:
        log_path = str(record.get("log_path") or "")
        if not log_path:
            return
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(f"{log_entry['created_at']} [{log_entry['level']}] {log_entry['message']}\n")

    def _step(self, key: str, status: str, created_at: str, message: str) -> dict[str, Any]:
        return {"key": key, "status": status, "updated_at": created_at, "message": message}

    def _fail_steps(self, steps: list[dict[str, Any]], entry: dict[str, str]) -> list[dict[str, Any]]:
        return [*steps, self._step("run", "failed", entry["created_at"], entry["message"])]

    def _reset_steps(self, steps: list[dict[str, Any]], entry: dict[str, str]) -> list[dict[str, Any]]:
        return [step for step in steps if step.get("status") != "failed"] + [self._step("retry", "done", entry["created_at"], entry["message"])]

    def _write_metadata(self, record: dict[str, Any]) -> None:
        work_dir = self._work_dir_from_record(record)
        if not work_dir:
            return
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "work.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_path(self, path: Path) -> dict[str, Any]:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)], **config.subprocess_no_window())
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)], **config.subprocess_no_window())
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "path": str(path)}

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

    def _output_path(self, work: dict[str, Any]) -> Path | None:
        work_dir = self._work_dir_from_record(work)
        if not work_dir:
            return None
        for relative in ("output/final.wav", "inference/ai_vocal.wav"):
            path = work_dir / relative
            if path.is_file():
                return path
        return None

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

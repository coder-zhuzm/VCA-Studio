"""Work metadata creation and lookup service."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from application.inference_runner import InferenceRunner
from application.runtime_service import RuntimeService
from application.segment_builder import build_segments
from application.stem_preparer import StemPreparer
from application.stitch_service import StitchService
from infrastructure.storage import ListRepository
from infrastructure.uvr_tool import UvrTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _params(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    device = str(params.get("device") or "auto").strip()
    if device not in {"auto", "cpu", "cuda", "mps"}:
        device = "auto"
    try:
        transpose = int(params.get("transpose") or 0)
    except (TypeError, ValueError):
        transpose = 0

    f0_method = str(params.get("f0_method") or "rmvpe").strip()
    if f0_method not in {"rmvpe", "harvest", "crepe"}:
        f0_method = "rmvpe"

    f0_predictor = str(params.get("f0_predictor") or "rmvpe").strip()
    if f0_predictor not in {"rmvpe", "pm", "dio", "harvest", "crepe"}:
        f0_predictor = "rmvpe"

    method = str(params.get("method") or "reconstruct").strip()
    if method not in {"reconstruct", "cluster"}:
        method = "reconstruct"

    try:
        speaker = int(params.get("speaker") or 0)
    except (TypeError, ValueError):
        speaker = 0

    def number(key: str, default: float) -> float:
        try:
            return float(params.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "transpose": transpose,
        "device": device,
        "f0_method": f0_method,
        "index_rate": number("index_rate", 0.75),
        "rms_mix_rate": number("rms_mix_rate", 1),
        "protect": number("protect", 0.33),
        "filter_radius": int(number("filter_radius", 3)),
        "f0_predictor": f0_predictor,
        "method": method,
        "speaker": speaker,
        "cluster_ratio": number("cluster_ratio", 0),
        "shallow_diffusion": bool(params.get("shallow_diffusion")),
    }


class WorkService:
    def __init__(
        self,
        repo: ListRepository,
        stem_preparer: StemPreparer,
        model_repo: ListRepository | None = None,
        runtime: RuntimeService | None = None,
        inference_runner: InferenceRunner | None = None,
        uvr_tool: UvrTool | None = None,
    ) -> None:
        self._repo = repo
        self._stem_preparer = stem_preparer
        self._model_repo = model_repo
        self._runtime = runtime
        self._inference_runner = inference_runner
        self._uvr_tool = uvr_tool
        self._stitch = StitchService(getattr(stem_preparer, "_ffmpeg_path", ""))
        self._queue: queue.Queue[str] = queue.Queue()
        self._queued: set[str] = set()
        self._queue_lock = threading.Lock()
        self._worker = threading.Thread(target=self._run_queue, daemon=True)
        self._worker.start()

    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "无效的创建参数。"}
        models = self._read_models(payload)
        if not models:
            return {"ok": False, "error": "缺少目标模型。"}
        missing = [entry["model_id"] for entry in models if self._model_repo and not self._model_repo.get(entry["model_id"])]
        if missing:
            return {"ok": False, "error": f"模型不存在: {missing[0]}"}
        prepared = self._stem_preparer.prepare(payload)
        if not prepared.get("ok"):
            return {"ok": False, "error": str(prepared.get("error") or "输入准备失败。")}

        created_at = _now()
        input_files = self._input_files(prepared.get("files") or {}, payload)
        work_dir = self._work_dir_from_input_files(input_files)
        segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
        log_entry = {
            "level": "info",
            "message": "Input prepared",
            "created_at": created_at,
        }
        record = {
            "id": str(prepared["work_id"]),
            "name": str(payload.get("name") or "").strip() or "Untitled Work",
            "model_id": models[0]["model_id"],
            "models": models,
            "params": _params(payload),
            "segments": segments,
            "input_mode": str(prepared["mode"]),
            "skip_dereverb": bool((payload.get("params") or {}).get("skip_dereverb")),
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

    def _read_models(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw = payload.get("models")
        models: list[dict[str, Any]] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                model_id = str(item.get("model_id") or "").strip()
                if not model_id:
                    continue
                params = item.get("params") if isinstance(item.get("params"), dict) else {}
                models.append({"model_id": model_id, "params": params})
        if models:
            return models
        model_id = str(payload.get("model_id") or "").strip()
        if model_id:
            return [{"model_id": model_id, "params": _params(payload)}]
        return []

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

        if not self._inference_runner:
            return {"ok": True, "work": self._fail_work(work, "RVC runner 未配置。")}
        started = self._mark_running(work)
        self._enqueue(str(started["id"]))
        return {"ok": True, "work": started}

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
        with self._queue_lock:
            self._queued.discard(str(work_id))
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
        models = self._work_models(work)
        if not models:
            return "作品未指定模型。"
        frameworks: set[str] = set()
        for entry in models:
            model = self._model_repo.get(entry["model_id"]) if self._model_repo else None
            if not model:
                return f"模型不存在: {entry['model_id']}"
            framework = str(model.get("framework") or "rvc")
            if framework not in {"rvc", "so-vits-svc"}:
                return "P0 当前只支持 RVC / So-VITS-SVC 推理。"
            checkpoint = str((model.get("files") or {}).get("checkpoint") or "")
            if not checkpoint or not Path(checkpoint).is_file():
                return "主模型文件缺失。"
            frameworks.add(framework)
        for model_id in self._segment_model_ids(work):
            if not self._model_repo.get(model_id):
                return f"片段指派模型不存在: {model_id}"
        if self._runtime:
            for framework in frameworks:
                component = "svc" if framework == "so-vits-svc" else "rvc"
                status = self._runtime.check_component(component)
                if status.get("status") != "ready":
                    return f"{framework} runtime 未就绪：{status.get('message') or '未配置'}"
        if work.get("input_mode") == "song":
            source = self._song_path(work)
            if not source or not Path(source).is_file():
                return "完整歌曲输入文件缺失。"
        else:
            vocals_path = self._vocals_path(work)
            if not vocals_path or not Path(vocals_path).is_file():
                return "人声输入文件缺失。"
        return ""

    def _run_work(self, work_id: str) -> None:
        work = self._repo.get(work_id)
        if not work or not self._inference_runner:
            return
        if work.get("input_mode") == "song":
            work = self._separate(work)
            if work.get("status") == "failed":
                return
        models = self._work_models(work)
        if not models:
            self._fail_work(work, "作品未指定模型。")
            return
        work = self._mark_inference_start(work)
        try:
            ai_vocal = self._render_models(work, models)
        except Exception as exc:  # noqa: BLE001 - surface any render failure to the work log
            self._fail_work(work, str(exc) or "渲染失败。")
            return
        self._finish_work(work, ai_vocal)

    def _render_models(self, work: dict[str, Any], models: list[dict[str, Any]]) -> str:
        vocals = self._vocals_path(work)
        work_dir = self._work_dir_from_record(work)
        if not work_dir:
            raise RuntimeError("Work directory not found")
        renders = work_dir / "renders"
        full_paths: dict[str, str] = {}
        for entry in models:
            model = self._model_repo.get(entry["model_id"]) if self._model_repo else None
            if not model:
                raise RuntimeError(f"模型缺失: {entry['model_id']}")
            per_work = {**work, "params": entry.get("params") or work.get("params") or {}}
            out = renders / entry["model_id"] / "full.wav"
            result = self._inference_runner.run_rvc(per_work, model, vocals, str(out))
            if not result.get("ok"):
                raise RuntimeError(str(result.get("error") or "推理失败。"))
            full_paths[entry["model_id"]] = str(out)

        segments = work.get("segments") or []
        if segments:
            default_model = models[0]["model_id"]
            duration = self._audio_duration(vocals)
            normalized = build_segments(segments, "", default_model, duration)
            merged = work_dir / "inference" / "merged_vocal.wav"
            self._stitch.stitch(normalized, full_paths, vocals, str(merged), str(work.get("log_path") or work_dir / "run.log"))
            return str(merged)
        return full_paths[models[0]["model_id"]]

    def _separate(self, work: dict[str, Any]) -> dict[str, Any]:
        work_dir = self._work_dir_from_record(work)
        if not work_dir:
            return self._fail_work(work, "Work directory not found")
        source = Path(self._song_path(work))
        if not source.is_file():
            return self._fail_work(work, "完整歌曲输入文件缺失。")
        sep_dir = work_dir / "separated"
        sep_dir.mkdir(parents=True, exist_ok=True)
        vocals_out = sep_dir / "vocals.wav"
        instrumental_out = sep_dir / "instrumental.wav"

        work = self._mark_step(work, "separate", "running", "UVR 分离开始", 30, "separating")

        do_dereverb = not bool(work.get("skip_dereverb")) and bool(self._uvr_tool and self._uvr_tool.available_dereverb())
        if not self._uvr_tool or not self._uvr_tool.available():
            self._log(work, "UVR 未配置，降级使用原音频作为人声。", "warning")
            vocals_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, vocals_out)
            result: dict[str, Any] = {"ok": True, "vocals": str(vocals_out), "instrumental": ""}
        else:
            result = self._uvr_tool.separate(source, vocals_out, instrumental_out, do_dereverb)
            if not result.get("ok"):
                self._log(work, f"UVR 分离失败，降级使用原音频作为人声：{result.get('error')}", "error")
                vocals_out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, vocals_out)
                result = {"ok": True, "vocals": str(vocals_out), "instrumental": ""}

        files = [f for f in (work.get("input_files") or []) if f.get("role") not in ("vocals", "instrumental")]
        files.append({
            "role": "vocals",
            "source_path": str(source),
            "stored_path": str(result.get("vocals")),
            "filename": Path(str(result.get("vocals"))).name,
        })
        if result.get("instrumental"):
            files.append({
                "role": "instrumental",
                "source_path": str(source),
                "stored_path": str(result.get("instrumental")),
                "filename": Path(str(result.get("instrumental"))).name,
            })
        work = {**work, "input_files": files}
        work = self._mark_step(work, "separate", "done", "UVR 分离完成", 60, "separating")
        self._write_metadata(work)
        self._repo.update_item(str(work["id"]), work)
        return work

    def _enqueue(self, work_id: str) -> None:
        with self._queue_lock:
            if work_id in self._queued:
                return
            self._queued.add(work_id)
            self._queue.put(work_id)

    def _run_queue(self) -> None:
        while True:
            work_id = self._queue.get()
            try:
                self._run_work(work_id)
            finally:
                with self._queue_lock:
                    self._queued.discard(work_id)
                self._queue.task_done()

    def _vocals_path(self, work: dict[str, Any]) -> str:
        vocals = next((item for item in work.get("input_files") or [] if item.get("role") == "vocals"), None)
        return str((vocals or {}).get("stored_path") or "")

    def _song_path(self, work: dict[str, Any]) -> str:
        song = next((item for item in work.get("input_files") or [] if item.get("role") == "input_song"), None)
        return str((song or {}).get("stored_path") or "")

    def _work_models(self, work: dict[str, Any]) -> list[dict[str, Any]]:
        models = work.get("models")
        if isinstance(models, list) and models:
            return [m for m in models if isinstance(m, dict) and m.get("model_id")]
        model_id = str(work.get("model_id") or "").strip()
        if model_id:
            return [{"model_id": model_id, "params": work.get("params") or {}}]
        return []

    def _segment_model_ids(self, work: dict[str, Any]) -> set[str]:
        ids: set[str] = set()
        for seg in work.get("segments") or []:
            for model_id in (seg.get("assigned_model_ids") or []):
                ids.add(str(model_id))
        return ids

    def _audio_duration(self, path: str) -> float | None:
        if not path or not Path(path).is_file():
            return None
        ffprobe = shutil.which("ffprobe") or "ffprobe"
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                **config.subprocess_no_window(),
            )
            return float(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

    def _mark_running(self, work: dict[str, Any]) -> dict[str, Any]:
        is_song = work.get("input_mode") == "song"
        entry = {"level": "info", "message": "Work started" + (" (分离+推理)" if is_song else ""), "created_at": _now()}
        updated = {
            **work,
            "status": "running",
            "stage": "separating" if is_song else "inferencing",
            "progress": 30 if is_song else 50,
            "logs": [*(work.get("logs") or []), entry],
            "updated_at": entry["created_at"],
        }
        self._append_log(updated, entry)
        self._write_metadata(updated)
        self._repo.update_item(str(updated["id"]), updated)
        return updated

    def _mark_inference_start(self, work: dict[str, Any]) -> dict[str, Any]:
        return self._mark_step(work, "run", "running", "RVC inference started", 60, "inferencing")

    def _mark_step(self, work: dict[str, Any], key: str, status: str, message: str, progress: int | None = None, stage: str | None = None) -> dict[str, Any]:
        now = _now()
        entry = {"level": "info", "message": message, "created_at": now}
        patch: dict[str, Any] = {
            "steps": [
                *(step for step in (work.get("steps") or []) if step.get("key") != key),
                self._step(key, status, now, message),
            ],
            "logs": [*(work.get("logs") or []), entry],
            "updated_at": now,
        }
        if progress is not None:
            patch["progress"] = progress
        if stage is not None:
            patch["stage"] = stage
        updated = {**work, **patch}
        self._append_log(updated, entry)
        self._write_metadata(updated)
        self._repo.update_item(str(updated["id"]), updated)
        return updated

    def _log(self, work: dict[str, Any], message: str, level: str = "info") -> dict[str, Any]:
        now = _now()
        entry = {"level": level, "message": message, "created_at": now}
        updated = {**work, "logs": [*(work.get("logs") or []), entry], "updated_at": now}
        self._append_log(updated, entry)
        self._write_metadata(updated)
        self._repo.update_item(str(updated["id"]), updated)
        return updated

    def _finish_work(self, work: dict[str, Any], ai_vocal_path: str) -> dict[str, Any]:
        work_dir = self._work_dir_from_record(work)
        if not work_dir:
            return self._fail_work(work, "Work directory not found")
        source = Path(ai_vocal_path)
        target = work_dir / "output" / "final.wav"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            instrumental = self._instrumental_path(work)
            if instrumental:
                self._mix_final(source, Path(instrumental), target)
            else:
                shutil.copy2(source, target)
            if not target.is_file():
                raise OSError("输出文件未生成。")
        except (OSError, subprocess.SubprocessError) as exc:
            return self._fail_work(work, str(exc))
        entry = {"level": "info", "message": "RVC inference finished", "created_at": _now()}
        updated = {
            **work,
            "status": "done",
            "stage": "exported",
            "progress": 100,
            "output_files": {"ai_vocal": str(source), "final": str(target)},
            "steps": [
                *(step for step in (work.get("steps") or []) if step.get("key") != "run"),
                self._step("run", "done", entry["created_at"], entry["message"]),
            ],
            "logs": [*(work.get("logs") or []), entry],
            "updated_at": entry["created_at"],
        }
        self._append_log(updated, entry)
        self._write_metadata(updated)
        self._repo.update_item(str(updated["id"]), updated)
        return updated

    def _instrumental_path(self, work: dict[str, Any]) -> str:
        instrumental = next((item for item in work.get("input_files") or [] if item.get("role") == "instrumental"), None)
        path = str((instrumental or {}).get("stored_path") or "")
        return path if path and Path(path).is_file() else ""

    def _mix_final(self, vocal: Path, instrumental: Path, target: Path) -> None:
        ffmpeg = getattr(self._stem_preparer, "_ffmpeg_path", "")
        if not ffmpeg:
            raise OSError("混音需要先配置 ffmpeg。")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(instrumental), "-i", str(vocal), "-filter_complex", "amix=inputs=2:duration=longest", str(target)],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            **config.subprocess_no_window(),
        )

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
        return [*(step for step in steps if step.get("key") != "run"), self._step("run", "failed", entry["created_at"], entry["message"])]

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

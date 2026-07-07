"""Lightweight input preparation for vocal conversion works."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

_MODE_REQUIREMENTS = {
    "song": (("song_path", "input_song"),),
    "vocals": (("vocals_path", "vocals"),),
    "stems": (("vocals_path", "vocals"), ("instrumental_path", "instrumental")),
}


class StemPreparer:
    def __init__(self, works_dir: Path, ffmpeg_path: str = "") -> None:
        self._works_dir = works_dir
        self._ffmpeg_path = ffmpeg_path
        self._works_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload or {}
        mode = str(payload.get("mode") or "").strip()
        requirements = _MODE_REQUIREMENTS.get(mode)
        if not requirements:
            return {"ok": False, "error": "不支持的输入模式。"}

        sources: list[tuple[Path, str]] = []
        for field, role in requirements:
            raw = str(payload.get(field) or "").strip()
            if not raw:
                return {"ok": False, "error": f"缺少必填文件: {field}"}
            source = Path(raw).expanduser()
            if not source.is_file():
                return {"ok": False, "error": f"文件不存在: {raw}"}
            sources.append((source, role))

        work_id = f"work_{uuid.uuid4().hex[:12]}"
        work_dir = self._works_dir / work_id
        input_dir = work_dir / "input"
        try:
            input_dir.mkdir(parents=True, exist_ok=False)
            files = self._copy_sources(sources, input_dir, bool(payload.get("normalize_input")))
        except (OSError, subprocess.SubprocessError) as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "work_id": work_id, "mode": mode, "files": files}

    def _copy_sources(self, sources: list[tuple[Path, str]], input_dir: Path, normalize: bool) -> dict[str, str]:
        files: dict[str, str] = {}
        for source, role in sources:
            target = input_dir / f"{role}.wav"
            if normalize and self._ffmpeg_path:
                subprocess.run(
                    [self._ffmpeg_path, "-y", "-i", str(source), "-ar", "44100", "-ac", "2", str(target)],
                    capture_output=True,
                    check=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                )
            else:
                target = input_dir / f"{role}{source.suffix.lower()}"
                shutil.copy2(source, target)
            files[role] = str(target)
        return files

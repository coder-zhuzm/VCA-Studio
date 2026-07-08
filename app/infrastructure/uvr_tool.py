"""Thin wrapper around the UVR separation worker.

Invokes the configured UVR Python interpreter to run `uvr_worker.py` in a
subprocess and parses its JSON result line from stdout.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import config


class UvrTool:
    def __init__(self, uvr_python: str, model_dir: str) -> None:
        self._uvr_python = str(uvr_python or "").strip()
        self._model_dir = str(model_dir or "").strip()
        self._worker = Path(__file__).parent / "uvr_worker.py"

    def available(self) -> bool:
        return bool(self._uvr_python) and Path(self._uvr_python).expanduser().is_file()

    def available_dereverb(self) -> bool:
        if not self._model_dir:
            return False
        return Path(self._model_dir).expanduser().joinpath("UVR-DeEcho-DeReverb.pth").is_file()

    def separate(self, source: Path, vocals_out: Path, instrumental_out: Path, do_dereverb: bool) -> dict[str, Any]:
        if not self.available():
            return {"ok": False, "error": "UVR Python 未配置"}
        command = [
            str(Path(self._uvr_python).expanduser()),
            str(self._worker),
            "--input",
            str(source),
            "--model_dir",
            self._model_dir,
            "--vocals_out",
            str(vocals_out),
            "--instrumental_out",
            str(instrumental_out),
        ]
        if do_dereverb:
            command.append("--do_dereverb")
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=None,
                **config.subprocess_no_window(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": str(exc)}
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() or f"UVR 退出码 {proc.returncode}"
            return {"ok": False, "error": detail}
        data = self._parse_result(proc.stdout or "")
        if not data.get("ok"):
            return {"ok": False, "error": str(data.get("error") or "UVR 分离失败")}
        return data

    @staticmethod
    def _parse_result(stdout: str) -> dict[str, Any]:
        for line in stdout.splitlines():
            if line.startswith("UVR_RESULT "):
                try:
                    return json.loads(line[len("UVR_RESULT "):])
                except (ValueError, TypeError):
                    return {"ok": False, "error": "UVR 输出解析失败"}
        return {"ok": False, "error": "UVR 未返回结果"}

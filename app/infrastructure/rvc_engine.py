"""RVC inference engine backed by `rvc_python`."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import config
from infrastructure.storage import SettingsStore


class RvcEngine:
    framework = "rvc"

    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

    def available(self) -> bool:
        python = str(self._settings.get("rvc_python", "") or "").strip()
        return bool(python) and Path(python).expanduser().is_file()

    def infer(self, model: dict[str, Any], vocals_path: str, out_path: str, params: dict[str, Any], log_path: str) -> dict[str, Any]:
        command = self._command(model, vocals_path, out_path, params)
        try:
            with Path(log_path).open("a", encoding="utf-8") as log:
                log.write("RVC command: " + " ".join(command) + "\n")
                result = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=None,
                    **config.subprocess_no_window(),
                )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {"ok": False, "error": f"RVC 推理失败，退出码 {result.returncode}"}
        if not Path(out_path).is_file():
            return {"ok": False, "error": "RVC 推理未生成输出文件。"}
        return {"ok": True, "path": out_path}

    def _command(self, model: dict[str, Any], vocals_path: str, out_path: str, params: dict[str, Any]) -> list[str]:
        files = model.get("files") or {}
        command = [
            str(Path(str(self._settings.get("rvc_python", "")).expanduser())),
            "-m",
            "rvc_python",
            "infer_file",
            "--input_path",
            vocals_path,
            "--model_path",
            str(files.get("checkpoint") or ""),
            "--output_path",
            out_path,
            "--f0method",
            str(params.get("f0_method") or "rmvpe"),
            "--f0up_key",
            str(params.get("transpose") or 0),
            "--index_rate",
            str(params.get("index_rate") or 0.75),
            "--protect",
            str(params.get("protect") or 0.33),
        ]
        index = str(files.get("index") or "")
        if index:
            command.extend(["--index_path", index])
        return command

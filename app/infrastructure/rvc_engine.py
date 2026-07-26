"""RVC inference engine backed by the `rvc-python` package CLI.

Real CLI surface (verified against rvc-python docs):
    python -m rvc_python cli -i INPUT -o OUTPUT -mp MODEL [options]
with short options `-me` (f0 method), `-pi` (pitch/transpose), `-ir`
(index rate), `-pr` (protect), `-fr` (filter radius), `-rmr`
(rms mix rate), `-de` (device, e.g. "cuda:0"/"cpu"/"mps"), `-ip` (index path).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import config
from infrastructure.proc_slot import SLOT
from infrastructure.storage import SettingsStore


def resolve_device(device: str) -> str:
    """Map UI device value to rvc-python's device string. Resolve `auto` via host probe."""
    device = str(device or "auto").strip()
    if device == "auto":
        try:
            from application.host_probe import probe_host

            device = str(probe_host().get("recommended_device") or "cpu")
        except Exception:  # noqa: BLE001 - probing must never break inference
            device = "cpu"
    if device == "cuda":
        return "cuda:0"
    return device


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
                result = SLOT.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
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
            str(Path(str(self._settings.get("rvc_python", "") or "")).expanduser()),
            "-m",
            "rvc_python",
            "cli",
            "-i",
            vocals_path,
            "-o",
            out_path,
            "-mp",
            str(files.get("checkpoint") or ""),
            "-me",
            str(params.get("f0_method") or "rmvpe"),
            "-pi",
            str(params.get("transpose") or 0),
            "-ir",
            str(params.get("index_rate") if params.get("index_rate") is not None else 0.75),
            "-pr",
            str(params.get("protect") if params.get("protect") is not None else 0.33),
            "-fr",
            str(int(params.get("filter_radius") or 3)),
            "-rmr",
            str(params.get("rms_mix_rate") if params.get("rms_mix_rate") is not None else 1),
            "-de",
            resolve_device(str(params.get("device") or "auto")),
        ]
        index = str(files.get("index") or "")
        if index:
            command.extend(["-ip", index])
        return command

"""So-VITS-SVC inference engine backed by `svc_worker.py`.

Runs the worker under the configured `svc_python` inside the configured
So-VITS-SVC repository. The worker drives `inference.infer_tool.Svc` directly
(stable across 4.0/4.1 forks) instead of guessing a CLI surface, and reports a
single `SVC_RESULT {json}` line on stdout.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import config
from infrastructure.rvc_engine import resolve_device
from infrastructure.storage import SettingsStore


class SvcEngine:
    framework = "so-vits-svc"

    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings
        self._worker = Path(__file__).parent / "svc_worker.py"

    def available(self) -> bool:
        python = str(self._settings.get("svc_python", "") or "").strip()
        repo = str(self._settings.get("sovits_repo", "") or "").strip()
        if not python or not Path(python).expanduser().is_file():
            return False
        if not repo:
            return False
        return Path(repo).expanduser().joinpath("inference", "infer_tool.py").is_file()

    def infer(self, model: dict[str, Any], vocals_path: str, out_path: str, params: dict[str, Any], log_path: str) -> dict[str, Any]:
        files = model.get("files") or {}
        checkpoint = str(files.get("checkpoint") or "")
        config_path = str(files.get("config") or "")
        if not checkpoint or not config_path:
            return {"ok": False, "error": "So-VITS-SVC 模型缺少主模型或 config。"}
        command = self._command(files, checkpoint, config_path, vocals_path, out_path, params)
        try:
            with Path(log_path).open("a", encoding="utf-8") as log:
                log.write("SVC command: " + " ".join(command) + "\n")
                proc = subprocess.run(
                    command,
                    cwd=str(Path(str(self._settings.get("sovits_repo", "") or "").strip()).expanduser()),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=None,
                    **config.subprocess_no_window(),
                )
                if proc.stdout:
                    log.write(proc.stdout)
                if proc.stderr:
                    log.write(proc.stderr)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": str(exc)}
        result = self._parse_result(proc.stdout or "")
        if not result.get("ok"):
            detail = str(result.get("error") or "").strip()
            if not detail and proc.returncode != 0:
                detail = f"So-VITS-SVC 推理失败，退出码 {proc.returncode}"
            return {"ok": False, "error": detail or "So-VITS-SVC 推理失败。"}
        if not Path(out_path).is_file():
            return {"ok": False, "error": "So-VITS-SVC 推理未生成输出文件。"}
        return {"ok": True, "path": out_path}

    def _command(
        self,
        files: dict[str, Any],
        checkpoint: str,
        config_path: str,
        vocals_path: str,
        out_path: str,
        params: dict[str, Any],
    ) -> list[str]:
        repo = str(Path(str(self._settings.get("sovits_repo", "") or "").strip()).expanduser())
        device = resolve_device(str(params.get("device") or "auto"))
        command = [
            str(Path(str(self._settings.get("svc_python", "") or "").strip()).expanduser()),
            str(self._worker),
            "--repo",
            repo,
            "--model",
            checkpoint,
            "--config",
            config_path,
            "--input",
            vocals_path,
            "--output",
            out_path,
            "--transpose",
            str(params.get("transpose") or 0),
            "--f0_predictor",
            str(params.get("f0_predictor") or "rmvpe"),
            "--device",
            device,
        ]
        speaker = str(params.get("speaker") or "").strip()
        if speaker:
            command.extend(["--speaker", speaker])
        cluster_ratio = float(params.get("cluster_ratio") or 0)
        cluster_model = str(files.get("cluster") or "")
        if cluster_ratio > 0 and cluster_model:
            command.extend(["--cluster_ratio", str(cluster_ratio), "--cluster_model", cluster_model])
        diffusion = str(files.get("diffusion") or "")
        if bool(params.get("shallow_diffusion")) and diffusion:
            command.append("--shallow_diffusion")
            command.extend(["--diffusion_model", diffusion])
            diffusion_config = str(files.get("diffusion_config") or "")
            if diffusion_config:
                command.extend(["--diffusion_config", diffusion_config])
        return command

    @staticmethod
    def _parse_result(stdout: str) -> dict[str, Any]:
        for line in stdout.splitlines():
            if line.startswith("SVC_RESULT "):
                try:
                    return json.loads(line[len("SVC_RESULT "):])
                except (ValueError, TypeError):
                    return {"ok": False, "error": "SVC 输出解析失败"}
        return {"ok": False, "error": ""}

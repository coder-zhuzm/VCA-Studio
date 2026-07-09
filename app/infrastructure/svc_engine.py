"""So-VITS-SVC inference engine backed by the project's `svc_python` and repo.

Invokes `inference/infer_tool.py` from the configured So-VITS-SVC repository. The
exact CLI surface varies across forks, so this implementation targets the
common 4.1 `infer_tool` flags and discovers the produced output file by scanning
the output directory. Validate against a real install before relying on it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import config
from infrastructure.storage import SettingsStore


class SvcEngine:
    framework = "so-vits-svc"

    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

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

        python = str(Path(str(self._settings.get("svc_python", "")).expanduser()))
        repo = str(Path(str(self._settings.get("sovits_repo", "")).expanduser()))
        diffusion = str(files.get("diffusion") or "")
        shallow = bool(params.get("shallow_diffusion")) and bool(diffusion)
        cluster_ratio = float(params.get("cluster_ratio") or 0)
        method = str(params.get("method") or "reconstruct")
        if cluster_ratio > 0 and method == "reconstruct":
            method = "cluster"

        with tempfile.TemporaryDirectory() as out_dir:
            command = [
                python,
                "-m",
                "inference.infer_tool",
                "-m",
                checkpoint,
                "-c",
                config_path,
                "-i",
                vocals_path,
                "-o",
                out_dir,
                "-k",
                str(params.get("transpose") or 0),
                "-f0p",
                str(params.get("f0_predictor") or "rmvpe"),
                "-meth",
                method,
                "-spk",
                str(params.get("speaker") or 0),
                "-shallow",
                str(shallow).lower(),
                "-diff",
                str(bool(diffusion)).lower(),
            ]
            if cluster_ratio > 0:
                command.extend(["-cr", str(cluster_ratio)])
            if shallow and diffusion:
                command.extend(["-dict", diffusion])

            try:
                with Path(log_path).open("a", encoding="utf-8") as log:
                    log.write("SVC command: " + " ".join(command) + "\n")
                    result = subprocess.run(
                        command,
                        cwd=repo,
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
                return {"ok": False, "error": f"So-VITS-SVC 推理失败，退出码 {result.returncode}"}

            produced = self._find_output(out_dir, Path(vocals_path).stem)
            if not produced:
                return {"ok": False, "error": "So-VITS-SVC 推理未生成输出文件。"}
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(produced, out_path)
        return {"ok": True, "path": out_path}

    @staticmethod
    def _find_output(out_dir: str, input_stem: str) -> str | None:
        candidates = [p for p in Path(out_dir).glob("*.wav")]
        if not candidates:
            return None
        for candidate in candidates:
            if candidate.stem != input_stem:
                return str(candidate)
        return str(candidates[0])

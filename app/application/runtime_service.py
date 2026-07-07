"""Runtime path persistence and lightweight component checks."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import config
from infrastructure.storage import SettingsStore

RUNTIME_PATH_KEYS = {
    "ffmpeg_path",
    "ffprobe_path",
    "svc_python",
    "sovits_repo",
    "rvc_python",
    "uvr_python",
    "uvr_model_dir",
}

_COMPONENTS = {
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffprobe",
    "svc": "So-VITS-SVC",
    "rvc": "RVC",
    "uvr": "UVR",
}


class RuntimeService:
    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "components": [self.check_component(key) for key in _COMPONENTS],
            "paths": self._paths(),
        }

    def set_path(self, key: str, path: str) -> dict[str, Any]:
        return self.set_paths({key: path})

    def set_paths(self, paths: dict[str, Any]) -> dict[str, Any]:
        cleaned = {str(key or ""): str(value or "").strip() for key, value in (paths or {}).items()}
        invalid = [key for key in cleaned if key not in RUNTIME_PATH_KEYS]
        if invalid:
            return {"ok": False, "error": f"未知运行环境路径: {invalid[0]}", **self.status()}
        self._settings.update(cleaned)
        return {"ok": True, **self.status()}

    def check_component(self, key: str) -> dict[str, Any]:
        key = str(key or "")
        if key == "ffmpeg":
            return self._check_command("ffmpeg", "ffmpeg_path", "ffmpeg")
        if key == "ffprobe":
            return self._check_command("ffprobe", "ffprobe_path", "ffprobe")
        if key == "svc":
            return self._component("svc", [
                self._file_check("svc_python", "SVC Python"),
                self._sovits_repo_check(),
                self._python_import_check("svc_python", "torch", "torch"),
                self._python_import_check("svc_python", "librosa", "librosa"),
                self._python_import_check("svc_python", "fairseq", "fairseq"),
            ])
        if key == "rvc":
            return self._component("rvc", [
                self._file_check("rvc_python", "RVC Python"),
                self._python_import_check("rvc_python", "torch", "torch"),
                self._python_import_check("rvc_python", "rvc_python", "rvc_python"),
            ])
        if key == "uvr":
            return self._component("uvr", [
                self._file_check("uvr_python", "UVR Python"),
                self._python_import_check("uvr_python", "audio_separator", "audio_separator"),
                self._dir_check("uvr_model_dir", "UVR 模型目录"),
                self._uvr_model_check("5_HP-Karaoke-UVR.pth"),
                self._uvr_model_check("UVR-DeEcho-DeReverb.pth"),
            ])
        return {
            "key": key,
            "name": key or "unknown",
            "status": "missing",
            "message": "未知组件",
            "checks": [],
        }

    def _paths(self) -> dict[str, str]:
        return {key: str(self._settings.get(key, "") or "") for key in sorted(RUNTIME_PATH_KEYS)}

    def _check_command(self, key: str, setting_key: str, exe: str) -> dict[str, Any]:
        configured = str(self._settings.get(setting_key, "") or "").strip()
        configured_path = Path(configured).expanduser() if configured else None
        candidate = str(configured_path) if configured_path else shutil.which(exe) or ""
        exists = bool(candidate and (Path(candidate).exists() or shutil.which(candidate)))
        checks = [{
            "key": setting_key,
            "label": f"{exe} 路径",
            "ok": exists,
            "message": candidate if exists else f"未找到 {exe}",
        }]
        if exists:
            checks.append(self._version_check(candidate, exe))
        return self._component(key, checks)

    def _version_check(self, command: str, label: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [command, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                **config.subprocess_no_window(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"key": f"{label}_version", "label": f"{label} 版本", "ok": False, "status": "error", "message": str(exc)}
        first = (result.stdout or result.stderr or "").splitlines()[0] if (result.stdout or result.stderr) else ""
        return {
            "key": f"{label}_version",
            "label": f"{label} 版本",
            "ok": result.returncode == 0,
            "message": first or f"退出码 {result.returncode}",
        }

    def _file_check(self, setting_key: str, label: str) -> dict[str, Any]:
        value = str(self._settings.get(setting_key, "") or "").strip()
        ok = bool(value and Path(value).expanduser().is_file())
        return {"key": setting_key, "label": label, "ok": ok, "message": value if ok else f"未配置或文件不存在: {label}"}

    def _dir_check(self, setting_key: str, label: str) -> dict[str, Any]:
        value = str(self._settings.get(setting_key, "") or "").strip()
        ok = bool(value and Path(value).expanduser().is_dir())
        return {"key": setting_key, "label": label, "ok": ok, "message": value if ok else f"未配置或目录不存在: {label}"}

    def _sovits_repo_check(self) -> dict[str, Any]:
        value = str(self._settings.get("sovits_repo", "") or "").strip()
        target = Path(value).expanduser() / "inference" / "infer_tool.py" if value else Path()
        ok = bool(value and target.is_file())
        return {"key": "sovits_repo", "label": "So-VITS-SVC 仓库", "ok": ok, "message": value if ok else "未找到 inference/infer_tool.py"}

    def _python_import_check(self, setting_key: str, module: str, label: str) -> dict[str, Any]:
        value = str(self._settings.get(setting_key, "") or "").strip()
        if not value or not Path(value).expanduser().is_file():
            return {"key": f"{setting_key}_{module}", "label": f"{label} import", "ok": False, "message": "Python 未配置"}
        try:
            result = subprocess.run(
                [str(Path(value).expanduser()), "-c", f"import {module}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                **config.subprocess_no_window(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"key": f"{setting_key}_{module}", "label": f"{label} import", "ok": False, "status": "error", "message": str(exc)}
        message = "可导入" if result.returncode == 0 else (result.stderr or result.stdout or f"退出码 {result.returncode}").strip()
        return {"key": f"{setting_key}_{module}", "label": f"{label} import", "ok": result.returncode == 0, "message": message}

    def _uvr_model_check(self, filename: str) -> dict[str, Any]:
        root = str(self._settings.get("uvr_model_dir", "") or "").strip()
        path = Path(root).expanduser() / filename if root else Path(filename)
        ok = bool(root and path.is_file())
        return {"key": filename, "label": filename, "ok": ok, "message": str(path) if ok else "模型文件缺失"}

    def _component(self, key: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
        ok_count = sum(1 for check in checks if check.get("ok"))
        if any(check.get("status") == "error" for check in checks):
            status = "error"
            message = "检测失败"
        elif checks and ok_count == len(checks):
            status = "ready"
            message = "已就绪"
        elif ok_count:
            status = "partial"
            message = "部分配置缺失"
        else:
            status = "missing"
            message = "未配置"
        return {"key": key, "name": _COMPONENTS.get(key, key), "status": status, "message": message, "checks": checks}

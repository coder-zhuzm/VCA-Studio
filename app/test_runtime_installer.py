"""RuntimeInstaller unit checks (no network, no real winget)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from application.runtime_installer import RuntimeInstaller
from application.runtime_service import RuntimeService
from infrastructure.storage import SettingsStore


def _installer(tmp: Path) -> RuntimeInstaller:
    settings = SettingsStore(tmp / "settings.json")
    runtime = RuntimeService(settings)
    return RuntimeInstaller(settings, runtime)


def test_resolve_prefers_configured_path() -> None:
    with tempfile.TemporaryDirectory() as root:
        tmp = Path(root)
        fake = tmp / "ffmpeg"
        fake.write_text("x")
        inst = _installer(tmp)
        inst._settings.set("ffmpeg_path", str(fake))
        resolved = inst._resolve_ffmpeg_paths()
        assert resolved is not None
        assert resolved[0] == str(fake)


def test_list_tasks_disables_winget_when_ffmpeg_ready() -> None:
    with tempfile.TemporaryDirectory() as root:
        tmp = Path(root)
        fake = tmp / "ffmpeg.exe"
        fake.write_text("x")
        inst = _installer(tmp)
        inst._settings.update({"ffmpeg_path": str(fake), "ffprobe_path": str(fake)})
        with patch("application.runtime_installer.sys.platform", "win32"), patch(
            "application.runtime_installer.shutil.which", return_value="winget"
        ), patch("application.runtime_installer.probe_host", return_value={
            "ok": True, "platform": "Windows", "machine": "AMD64",
            "gpu_name": "RTX 2060 SUPER", "cuda_detected": True,
            "recommended_device": "cuda", "notes": [],
        }):
            # Force ready via resolve seeing configured file
            tasks = {t["id"]: t for t in inst.list_tasks()["tasks"]}
        if "ffmpeg_winget" in tasks:
            assert tasks["ffmpeg_winget"]["available"] is False


def test_run_task_rejects_second_while_running() -> None:
    with tempfile.TemporaryDirectory() as root:
        inst = _installer(Path(root))
        inst._job = {"id": "rvc_venv_cuda", "status": "running", "message": "…", "progress": 10}
        result = inst.run_task("ffmpeg_path_hint")
        assert result.get("ok") is False
        assert "进行中" in str(result.get("error") or "")


def test_rvc_venv_cuda_available_tracks_rvc_ready() -> None:
    with tempfile.TemporaryDirectory() as root:
        tmp = Path(root)
        inst = _installer(tmp)
        profile = {
            "ok": True, "platform": "Windows", "machine": "AMD64",
            "gpu_name": "RTX 2060 SUPER", "cuda_detected": True,
            "recommended_device": "cuda", "notes": [],
        }
        rvc_py = tmp / "python.exe"
        rvc_py.write_text("x")
        inst._settings.set("rvc_python", str(rvc_py))
        with patch("application.runtime_installer.probe_host", return_value=profile):
            tasks = {t["id"]: t for t in inst.list_tasks()["tasks"]}
            if "rvc_venv_cuda" in tasks:
                assert tasks["rvc_venv_cuda"]["available"] is False
        inst._settings.set("rvc_python", "")
        with patch("application.runtime_installer.probe_host", return_value=profile):
            tasks = {t["id"]: t for t in inst.list_tasks()["tasks"]}
            assert "rvc_venv_cuda" in tasks
            assert tasks["rvc_venv_cuda"]["available"] is True


if __name__ == "__main__":
    test_resolve_prefers_configured_path()
    test_list_tasks_disables_winget_when_ffmpeg_ready()
    test_run_task_rejects_second_while_running()
    test_rvc_venv_cuda_available_tracks_rvc_ready()
    print("ok")

"""Optional runtime bootstrap: detect helpers and user-triggered install steps."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import config
from application.host_probe import probe_host
from application.runtime_service import RuntimeService
from infrastructure.storage import SettingsStore


class RuntimeInstaller:
    def __init__(self, settings: SettingsStore, runtime: RuntimeService) -> None:
        self._settings = settings
        self._runtime = runtime
        self._runtime_root = config.DATA_DIR / "runtime"
        self._log_path = config.DATA_DIR / "runtime_install.log"
        self._lock = threading.Lock()
        self._job: dict[str, Any] | None = None

    def host_profile(self) -> dict[str, Any]:
        return probe_host()

    def _resolve_ffmpeg_paths(self) -> tuple[str, str] | None:
        configured = str(self._settings.get("ffmpeg_path", "") or "").strip()
        if configured:
            p = Path(configured).expanduser()
            if p.is_file():
                fp = str(self._settings.get("ffprobe_path", "") or "").strip()
                if fp and Path(fp).expanduser().is_file():
                    return str(p), fp
                sibling = p.parent / "ffprobe"
                if sibling.is_file():
                    return str(p), str(sibling)
                return str(p), str(p)

        candidates: list[Path] = []
        for raw in (
            shutil.which("ffmpeg"),
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ):
            if raw:
                candidates.append(Path(raw).expanduser())
        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            probe = path.parent / "ffprobe"
            return str(path), str(probe) if probe.is_file() else str(path)
        return None

    def _ffmpeg_ready(self) -> bool:
        return self._resolve_ffmpeg_paths() is not None

    def _rvc_ready(self) -> bool:
        status = self._runtime.check_component("rvc")
        return status.get("status") == "ready"

    def detect_ffmpeg(self) -> dict[str, Any]:
        """Bind ffmpeg/ffprobe into settings and return runtime check snapshot."""
        resolved = self._resolve_ffmpeg_paths()
        if not resolved:
            return {
                "ok": False,
                "error": (
                    "未找到 ffmpeg。请先点「安装 ffmpeg（Homebrew）」或 brew install ffmpeg，"
                    "或在下方路径区手动填写 ffmpeg_path（混音与输入规范化必需）。"
                ),
            }
        ff, fp = resolved
        self._settings.update({"ffmpeg_path": ff, "ffprobe_path": fp})
        snap = self._runtime.status()
        return {
            "ok": True,
            "message": f"已绑定 ffmpeg：{ff}",
            "ffmpeg_path": ff,
            "ffprobe_path": fp,
            **snap,
        }

    def list_tasks(self) -> dict[str, Any]:
        profile = probe_host()
        tasks: list[dict[str, Any]] = []
        ffmpeg_ok = self._ffmpeg_ready()
        rvc_ready = self._rvc_ready()
        if sys.platform == "darwin" and shutil.which("brew"):
            tasks.append({
                "id": "ffmpeg_brew",
                "label": "安装 ffmpeg（Homebrew）",
                "description": "已安装可跳过；未安装时执行 brew install ffmpeg 并写入路径。",
                "risk": "需要 Homebrew 与网络。",
                "available": not ffmpeg_ok,
            })
        if sys.platform == "win32":
            tasks.append({
                "id": "ffmpeg_winget",
                "label": "安装 ffmpeg（winget）",
                "description": "通过 winget 安装 Gyan.FFmpeg。",
                "risk": "需要 winget 与网络；可能需管理员确认。",
                "available": not ffmpeg_ok and bool(shutil.which("winget")),
            })
        tasks.append({
            "id": "ffmpeg_path_hint",
            "label": "检测并绑定 ffmpeg",
            "description": "必需：混音、输入 WAV 规范化、试听都依赖 ffmpeg。从 PATH 或 Homebrew 路径写入配置。",
            "risk": "无",
            "available": True,
        })
        if profile.get("platform") == "Darwin" and profile.get("machine") == "arm64":
            tasks.append({
                "id": "rvc_venv_mps",
                "label": "创建 RVC 虚拟环境（Apple Silicon / MPS）",
                "description": f"在 {self._runtime_root / 'rvc'} 创建 venv，安装 PyTorch（MPS）+ rvc_python。",
                "risk": "下载体积大；首次推理可能较慢。",
                "available": not rvc_ready,
            })
        elif profile.get("cuda_detected"):
            tasks.append({
                "id": "rvc_venv_cuda",
                "label": "创建 RVC 虚拟环境（CUDA PyTorch + rvc_python）",
                "description": f"在 {self._runtime_root / 'rvc'} 创建 venv 并 pip 安装（约 5–15 分钟，需网络）。适配 {profile.get('gpu_name') or 'NVIDIA GPU'}。",
                "risk": "下载体积大；失败请查看 runtime_install.log。",
                "available": (not rvc_ready) and bool(profile.get("cuda_detected")),
            })
        else:
            label = "创建 RVC 虚拟环境（CPU PyTorch + rvc_python）"
            if profile.get("platform") == "Darwin":
                label = "创建 RVC 虚拟环境（macOS CPU）"
            tasks.append({
                "id": "rvc_venv_cpu",
                "label": label,
                "description": f"在 {self._runtime_root / 'rvc'} 创建 venv（无 CUDA）。",
                "risk": "下载体积大。",
                "available": (not rvc_ready) and not profile.get("cuda_detected"),
            })
        return {"ok": True, "profile": profile, "tasks": tasks}

    def install_status(self) -> dict[str, Any]:
        with self._lock:
            job = dict(self._job) if self._job else None
        return {"ok": True, "job": job, "log_path": str(self._log_path)}

    def run_task(self, task_id: str) -> dict[str, Any]:
        task_id = str(task_id or "").strip()
        with self._lock:
            if self._job and self._job.get("status") == "running":
                return {"ok": False, "error": "已有安装任务进行中，请稍候。"}

        if task_id == "ffmpeg_path_hint":
            return self.detect_ffmpeg()

        if task_id == "ffmpeg_brew":
            return self._start_job(task_id, self._install_ffmpeg_brew)

        if task_id == "ffmpeg_winget":
            return self._start_job(task_id, self._install_ffmpeg_winget)

        if task_id in ("rvc_venv_cuda", "rvc_venv_cpu", "rvc_venv_mps"):
            use_cuda = task_id == "rvc_venv_cuda"
            check_mps = task_id == "rvc_venv_mps"
            return self._start_job(task_id, lambda: self._bootstrap_rvc_venv(use_cuda, check_mps))

        return {"ok": False, "error": f"未知任务: {task_id}"}

    def _patch_job(self, message: str, progress: int | None = None) -> None:
        with self._lock:
            if not self._job or self._job.get("status") != "running":
                return
            patch: dict[str, Any] = {**self._job, "message": message[:500]}
            if progress is not None:
                patch["progress"] = max(0, min(100, int(progress)))
            self._job = patch

    def _start_job(self, task_id: str, target) -> dict[str, Any]:
        with self._lock:
            self._job = {"id": task_id, "status": "running", "message": "进行中…", "progress": 0}

        def worker() -> None:
            try:
                result = target()
                with self._lock:
                    self._job = {
                        "id": task_id,
                        "status": "done" if result.get("ok") else "failed",
                        "message": str(result.get("message") or result.get("error") or ""),
                        "progress": 100,
                        "result": result,
                    }
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._job = {"id": task_id, "status": "failed", "message": str(exc), "progress": 100}

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "message": "安装已在后台开始，请查看下方状态或 runtime_install.log。"}

    def _log(self, line: str) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")

    def _ensure_ffmpeg_paths(self) -> None:
        resolved = self._resolve_ffmpeg_paths()
        if resolved:
            ff, fp = resolved
            self._settings.update({"ffmpeg_path": ff, "ffprobe_path": fp})

    def _apply_ffmpeg_from_path(self) -> dict[str, Any]:
        return self.detect_ffmpeg()

    def _run_process_stream(self, command: list[str], label: str, timeout: int = 900) -> int:
        self._patch_job(f"{label}…", 15)
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **config.subprocess_no_window(),
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            self._log(line)
            stripped = line.strip()
            if stripped:
                self._patch_job(stripped[:240], None)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(f"{label} 超时")
        return proc.returncode

    def _install_ffmpeg_brew(self) -> dict[str, Any]:
        if not shutil.which("brew"):
            return {"ok": False, "error": "未找到 brew。"}
        self._log("=== brew install ffmpeg ===")
        code = self._run_process_stream(["brew", "install", "ffmpeg"], "brew install ffmpeg", timeout=900)
        if code != 0:
            return {"ok": False, "error": f"brew 退出码 {code}，详见 runtime_install.log"}
        self._ensure_ffmpeg_paths()
        bound = self.detect_ffmpeg()
        if bound.get("ok"):
            return {"ok": True, "message": bound.get("message")}
        applied = self._apply_ffmpeg_from_path()
        if not applied.get("ok"):
            brew_ff = Path("/opt/homebrew/bin/ffmpeg")
            intel_ff = Path("/usr/local/bin/ffmpeg")
            for candidate in (brew_ff, intel_ff):
                if candidate.is_file():
                    fp = candidate.parent / "ffprobe"
                    self._settings.update({
                        "ffmpeg_path": str(candidate),
                        "ffprobe_path": str(fp) if fp.is_file() else str(candidate),
                    })
                    return {"ok": True, "message": f"已写入 ffmpeg: {candidate}"}
            return {"ok": True, "message": "brew 已执行，请新开终端后点「仅检测 ffmpeg」。"}
        return {"ok": True, "message": applied.get("message")}

    def _install_ffmpeg_winget(self) -> dict[str, Any]:
        if not shutil.which("winget"):
            return {"ok": False, "error": "未找到 winget。"}
        self._log("=== winget install ffmpeg ===")
        code = self._run_process_stream(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "Gyan.FFmpeg",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            "winget install ffmpeg",
            timeout=600,
        )
        if code != 0:
            return {"ok": False, "error": f"winget 退出码 {code}，详见 runtime_install.log"}
        applied = self._apply_ffmpeg_from_path()
        if not applied.get("ok"):
            return {"ok": True, "message": "winget 已执行，但未自动发现 ffmpeg，请重启终端或手动填写路径。"}
        return {"ok": True, "message": applied.get("message")}

    def _bootstrap_rvc_venv(self, use_cuda: bool, check_mps: bool = False) -> dict[str, Any]:
        root = self._runtime_root / "rvc"
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        py = sys.executable
        self._log(f"=== create venv {root} with {py} ===")
        self._patch_job("创建 Python 虚拟环境…", 8)
        subprocess.run([py, "-m", "venv", str(root)], check=True, timeout=120, **config.subprocess_no_window())
        if sys.platform == "win32":
            vpy = root / "Scripts" / "python.exe"
            pip = root / "Scripts" / "pip.exe"
        else:
            vpy = root / "bin" / "python"
            pip = root / "bin" / "pip"

        pip_steps = [
            (["install", "-U", "pip", "wheel"], "升级 pip", 18),
            (
                ["install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu121"]
                if use_cuda
                else ["install", "torch", "torchvision", "torchaudio"],
                "安装 PyTorch",
                45,
            ),
            (["install", "rvc-python"], "安装 rvc-python", 78),
        ]

        def run_pip_stream(args: list[str], label: str, progress: int) -> None:
            self._log("pip " + " ".join(args))
            self._patch_job(label, progress)
            proc = subprocess.Popen(
                [str(pip), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **config.subprocess_no_window(),
            )
            assert proc.stdout is not None
            tail = ""
            for line in proc.stdout:
                self._log(line)
                stripped = line.strip()
                if stripped:
                    tail = stripped[:200]
                    self._patch_job(f"{label} — {tail}", progress)
            code = proc.wait(timeout=1800)
            if code != 0:
                raise RuntimeError(f"pip 失败: {' '.join(args)}")

        for args, label, prog in pip_steps:
            run_pip_stream(args, label, prog)
        if not vpy.is_file():
            return {"ok": False, "error": "venv 创建失败"}
        self._settings.set("rvc_python", str(vpy))
        self._patch_job("校验 torch / rvc_python…", 92)
        if check_mps:
            verify_script = (
                "import torch; import rvc_python; "
                "print('mps', getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available())"
            )
        elif use_cuda:
            verify_script = "import torch; import rvc_python; print('cuda', torch.cuda.is_available())"
        else:
            verify_script = "import torch; import rvc_python; print('ok', True)"
        verify = subprocess.run(
            [str(vpy), "-c", verify_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            **config.subprocess_no_window(),
        )
        self._log(verify.stdout or verify.stderr or "")
        msg = f"RVC 环境已写入 rvc_python={vpy}"
        if use_cuda and "cuda True" not in (verify.stdout or "").replace(",", " "):
            msg += "（警告：CUDA 不可用，请检查驱动）"
        if check_mps and "mps True" not in (verify.stdout or ""):
            msg += "（警告：MPS 不可用，新建翻唱请改设备为 cpu）"
        return {"ok": True, "message": msg, "rvc_python": str(vpy)}
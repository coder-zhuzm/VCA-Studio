"""Detect host OS/GPU and suggest inference device for the current machine."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from typing import Any

import config


def probe_host() -> dict[str, Any]:
    system = platform.system()
    machine = platform.machine()
    release = platform.release()
    processor = platform.processor() or ""

    gpu_name = ""
    cuda_available = False
    driver_version = ""
    if shutil.which("nvidia-smi"):
        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                **config.subprocess_no_window(),
            )
            if proc.returncode == 0 and proc.stdout.strip():
                line = proc.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                gpu_name = parts[0] if parts else ""
                driver_version = parts[1] if len(parts) > 1 else ""
                cuda_available = True
        except (OSError, subprocess.SubprocessError):
            pass

    recommended_device = "auto"
    notes: list[str] = []
    if system == "Darwin":
        recommended_device = "mps" if machine == "arm64" else "cpu"
        if machine == "arm64":
            notes.append("Apple Silicon：推理设备建议 mps；需 PyTorch 支持 MPS。")
        else:
            notes.append("Intel Mac：无 CUDA，推理请用 cpu。")
        notes.append("macOS 无 NVIDIA CUDA；ffmpeg 可用 Homebrew 安装。")
    elif system == "Windows" and cuda_available:
        recommended_device = "cuda"
        notes.append("检测到 NVIDIA GPU，翻唱参数设备建议选 cuda。")
        if re.search(r"2060|2070|2080|3060|3070|3080|4060|4070|4080|4090|50\d0", gpu_name, re.I):
            notes.append("消费级独显：RVC/SVC 请安装带 CUDA 的 PyTorch（与显卡驱动匹配）。")
    elif cuda_available:
        recommended_device = "cuda"
    else:
        recommended_device = "cpu"
        notes.append("未检测到 nvidia-smi，将使用 CPU 推理（较慢）。")

    return {
        "ok": True,
        "platform": system,
        "machine": machine,
        "os_release": release,
        "processor": processor,
        "gpu_name": gpu_name,
        "driver_version": driver_version,
        "cuda_detected": cuda_available,
        "recommended_device": recommended_device,
        "notes": notes,
    }
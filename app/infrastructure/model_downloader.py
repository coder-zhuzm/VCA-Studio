"""Download a model archive and auto-detect its files.

MVP for the model station (阶段 7): supports `http(s)` and `file` URLs, unpacks
a zip, and recognizes checkpoint / index / config / diffusion files so the
model can be registered without manual file picking.
"""

from __future__ import annotations

import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

_ROLES = ("checkpoint", "index", "config", "diffusion")


def download(url: str, dest: Path) -> Path:
    urllib.request.urlretrieve(str(url), str(dest))
    return dest


def inspect_zip(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]

    def find(suffix: str) -> str | None:
        for name in names:
            if name.split("/")[-1].lower().endswith(suffix):
                return name
        return None

    checkpoint = find(".pth") or find(".ckpt")
    index = find(".index")
    config = find("config.json")
    diffusion = find(".pt")
    if diffusion and diffusion == checkpoint:
        diffusion = None

    framework = "so-vits-svc" if config else "rvc"
    files: dict[str, str] = {}
    if checkpoint:
        files["checkpoint"] = checkpoint
    if index:
        files["index"] = index
    if config:
        files["config"] = config
    if diffusion:
        files["diffusion"] = diffusion
    return {"framework": framework, "files": files}


def extract_model(url: str, model_dir: Path) -> dict[str, Any]:
    """Download ``url``, unpack, and copy recognized files into ``model_dir``.

    Returns ``{"framework": str, "files": {role: path}}`` or raises on failure.
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "model.zip"
        download(url, zip_path)
        info = inspect_zip(zip_path)
        if not info["files"].get("checkpoint"):
            raise RuntimeError("压缩包中未找到模型主文件（.pth）。")
        extracted = Path(tmp) / "extracted"
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extracted)
        files: dict[str, str] = {}
        for role, zip_name in info["files"].items():
            src = extracted / zip_name
            if not src.is_file():
                continue
            dst = model_dir / f"{role}{src.suffix.lower()}"
            import shutil

            shutil.copy2(src, dst)
            files[role] = str(dst)
    return {"framework": info["framework"], "files": files}

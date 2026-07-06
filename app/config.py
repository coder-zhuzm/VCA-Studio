"""App metadata, paths, and runtime helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "VCA-Studio"
APP_TITLE = "VCA-Studio"
APP_VERSION = "0.1.0"
DATA_DIR_NAME = ".vca_studio"

_FROZEN = bool(getattr(sys, "frozen", False))
if _FROZEN:
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = Path(__file__).resolve().parent

ROOT_DIR = BASE_DIR
DIST_INDEX = BUNDLE_DIR / "web" / "dist" / "index.html" if _FROZEN else ROOT_DIR / "web" / "dist" / "index.html"


def _default_data_dir() -> Path:
    env = os.environ.get("VCA_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME / DATA_DIR_NAME
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / APP_NAME / DATA_DIR_NAME


DATA_DIR = _default_data_dir()
SETTINGS_DB = DATA_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"
MODELS_DB = DATA_DIR / "models.json"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def subprocess_no_window() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        "startupinfo": startupinfo,
    }

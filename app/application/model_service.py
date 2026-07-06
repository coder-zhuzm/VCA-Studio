"""Local voice model import and metadata management."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infrastructure.storage import ListRepository

FRAMEWORKS = {"rvc", "so-vits-svc"}
REQUIRED = {
    "rvc": ("checkpoint_path",),
    "so-vits-svc": ("checkpoint_path", "config_path"),
}
ROLES = {
    "checkpoint_path": "checkpoint",
    "index_path": "index",
    "config_path": "config",
    "diffusion_path": "diffusion",
    "diffusion_config_path": "diffusion_config",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelService:
    def __init__(self, repo: ListRepository, models_dir: Path) -> None:
        self._repo = repo
        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list[dict[str, Any]]:
        return self._repo.all()

    def import_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload or {}
        framework = str(payload.get("framework") or "").strip()
        if framework not in FRAMEWORKS:
            return {"ok": False, "error": "不支持的模型框架。"}
        error = self._validate_payload(framework, payload)
        if error:
            return {"ok": False, "error": error}

        model_id = f"model_{uuid.uuid4().hex[:12]}"
        model_dir = self._models_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            files = self._copy_files(payload, model_dir)
            first = len(self._repo.all()) == 0
            record = {
                "id": model_id,
                "name": str(payload.get("name") or "").strip() or framework,
                "framework": framework,
                "files": files,
                "status": "missing",
                "is_default": first,
                "created_at": _now(),
                "updated_at": _now(),
                "checks": [],
            }
            self._repo.add(record)
            checked = self.check_model(model_id)
            return {"ok": True, "model": checked["model"]}
        except OSError as exc:
            shutil.rmtree(model_dir, ignore_errors=True)
            return {"ok": False, "error": str(exc)}

    def delete_model(self, model_id: str) -> dict[str, Any]:
        model = self._repo.get(str(model_id))
        if not model:
            return {"ok": False, "error": "模型不存在。"}
        model_dir = self._model_dir(model)
        self._repo.remove(model["id"])
        if model_dir and self._is_inside_models_dir(model_dir):
            shutil.rmtree(model_dir, ignore_errors=True)
        self._ensure_default()
        return {"ok": True, "models": self.list_models()}

    def check_model(self, model_id: str) -> dict[str, Any]:
        model = self._repo.get(str(model_id))
        if not model:
            return {"ok": False, "error": "模型不存在。"}
        checks = self._checks(model)
        status = "ready" if checks and all(check["ok"] for check in checks) else "missing"
        updated = {**model, "status": status, "checks": checks, "updated_at": _now()}
        self._repo.update_item(model["id"], updated)
        return {"ok": True, "model": updated}

    def set_default_model(self, model_id: str) -> dict[str, Any]:
        model_id = str(model_id)
        if not self._repo.get(model_id):
            return {"ok": False, "error": "模型不存在。"}
        items = [{**model, "is_default": model.get("id") == model_id, "updated_at": _now()} for model in self._repo.all()]
        self._repo.replace_all(items)
        return {"ok": True, "models": self.list_models()}

    def _validate_payload(self, framework: str, payload: dict[str, Any]) -> str:
        for key in REQUIRED[framework]:
            path = Path(str(payload.get(key) or "")).expanduser()
            if not path.is_file():
                return f"缺少必填文件: {key}"
        return ""

    def _copy_files(self, payload: dict[str, Any], model_dir: Path) -> dict[str, str]:
        files: dict[str, str] = {}
        for source_key, role in ROLES.items():
            raw = str(payload.get(source_key) or "").strip()
            if not raw:
                continue
            src = Path(raw).expanduser()
            if not src.is_file():
                raise OSError(f"文件不存在: {raw}")
            name = "config.json" if role == "config" else f"{role}{src.suffix.lower()}"
            dst = model_dir / name
            shutil.copy2(src, dst)
            files[role] = str(dst)
        return files

    def _checks(self, model: dict[str, Any]) -> list[dict[str, Any]]:
        files = model.get("files") or {}
        checks = [self._file_check(files, "checkpoint", "主模型")]
        if model.get("framework") == "rvc":
            if files.get("index"):
                checks.append(self._file_check(files, "index", "RVC index"))
        else:
            checks.append(self._file_check(files, "config", "SVC config"))
            if files.get("diffusion"):
                checks.append(self._file_check(files, "diffusion", "浅扩散模型"))
            if files.get("diffusion_config"):
                checks.append(self._file_check(files, "diffusion_config", "浅扩散配置"))
        return checks

    def _file_check(self, files: dict[str, str], key: str, label: str) -> dict[str, Any]:
        value = str(files.get(key) or "")
        ok = bool(value and Path(value).is_file())
        return {"key": key, "label": label, "ok": ok, "message": value if ok else "文件缺失"}

    def _model_dir(self, model: dict[str, Any]) -> Path | None:
        files = model.get("files") or {}
        first = next(iter(files.values()), "")
        return Path(first).parent if first else None

    def _is_inside_models_dir(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._models_dir.resolve())
            return True
        except ValueError:
            return False

    def _ensure_default(self) -> None:
        items = self._repo.all()
        if not items or any(item.get("is_default") for item in items):
            return
        items[0] = {**items[0], "is_default": True, "updated_at": _now()}
        self._repo.replace_all(items)

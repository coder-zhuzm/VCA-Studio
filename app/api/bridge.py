"""pywebview JavaScript API bridge."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
from typing import Any

import webview

try:
    import config
    from application.inference_runner import InferenceRunner
    from application.model_service import ModelService
    from application.runtime_service import RuntimeService
    from application.stem_preparer import StemPreparer
    from application.work_service import WorkService
    from infrastructure.engine import EngineRegistry
    from infrastructure.rvc_engine import RvcEngine
    from infrastructure.svc_engine import SvcEngine
    from infrastructure.storage import ListRepository, SettingsStore
    from infrastructure.uvr_tool import UvrTool
except ModuleNotFoundError:
    app_dir = Path(__file__).resolve().parents[1]
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    import config
    from application.inference_runner import InferenceRunner
    from application.model_service import ModelService
    from application.runtime_service import RuntimeService
    from application.stem_preparer import StemPreparer
    from application.work_service import WorkService
    from infrastructure.engine import EngineRegistry
    from infrastructure.rvc_engine import RvcEngine
    from infrastructure.svc_engine import SvcEngine
    from infrastructure.storage import ListRepository, SettingsStore
    from infrastructure.uvr_tool import UvrTool


class Api:
    def __init__(
        self,
        settings: SettingsStore,
        runtime: RuntimeService,
        models: ModelService,
        stem_preparer: StemPreparer,
        works: WorkService,
    ) -> None:
        self._settings = settings
        self._runtime = runtime
        self._models = models
        self._stem_preparer = stem_preparer
        self._works = works
        self._window = None

    def set_window(self, window) -> None:  # noqa: ANN001
        self._window = window

    def get_app_status(self) -> dict[str, Any]:
        return {
            "name": config.APP_NAME,
            "title": config.APP_TITLE,
            "version": config.APP_VERSION,
            "data_dir": str(config.DATA_DIR),
            "dist_index": str(config.DIST_INDEX),
        }

    def get_settings(self) -> dict[str, Any]:
        return self._settings.all()

    def set_setting(self, key: str, value: Any) -> dict[str, Any]:
        self._settings.set(str(key), value)
        return {"ok": True, "settings": self._settings.all()}

    def choose_file(self) -> dict[str, Any]:
        if not self._window:
            return {"ok": False, "error": "Window not ready"}
        paths = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
        return {"ok": True, "path": str(paths[0]) if paths else ""}

    def choose_directory(self) -> dict[str, Any]:
        if not self._window:
            return {"ok": False, "error": "Window not ready"}
        paths = self._window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
        return {"ok": True, "path": str(paths[0]) if paths else ""}

    def open_data_dir(self) -> dict[str, Any]:
        return self._works.open_path(config.DATA_DIR)

    def get_runtime_status(self) -> dict[str, Any]:
        return self._runtime.status()

    def check_runtime_component(self, key: str) -> dict[str, Any]:
        return {"ok": True, "component": self._runtime.check_component(key), **self._runtime.status()}

    def set_runtime_path(self, key: str, path: str) -> dict[str, Any]:
        return self._runtime.set_path(key, path)

    def set_runtime_paths(self, paths: dict[str, Any]) -> dict[str, Any]:
        return self._runtime.set_paths(paths)

    def list_models(self) -> list[dict[str, Any]]:
        return self._models.list_models()

    def import_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._models.import_model(payload or {})

    def delete_model(self, model_id: str) -> dict[str, Any]:
        return self._models.delete_model(model_id)

    def check_model(self, model_id: str) -> dict[str, Any]:
        return self._models.check_model(model_id)

    def set_default_model(self, model_id: str) -> dict[str, Any]:
        return self._models.set_default_model(model_id)

    def open_model_dir(self, model_id: str) -> dict[str, Any]:
        return self._models.open_model_dir(model_id)

    def prepare_stems(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._stem_preparer.prepare(payload or {})

    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._works.create_work(payload or {})

    def list_works(self) -> dict[str, Any]:
        return self._works.list_works()

    def get_work(self, work_id: str) -> dict[str, Any]:
        return self._works.get_work(work_id)

    def start_work(self, work_id: str) -> dict[str, Any]:
        return self._works.start_work(work_id)

    def retry_work(self, work_id: str) -> dict[str, Any]:
        return self._works.retry_work(work_id)

    def rename_work(self, work_id: str, name: str) -> dict[str, Any]:
        return self._works.rename_work(work_id, name)

    def export_work(self, work_id: str, target_dir: str) -> dict[str, Any]:
        return self._works.export_work(work_id, target_dir)

    def delete_work(self, work_id: str) -> dict[str, Any]:
        return self._works.delete_work(work_id)

    def read_work_log(self, work_id: str) -> dict[str, Any]:
        return self._works.read_work_log(work_id)

    def open_work_dir(self, work_id: str) -> dict[str, Any]:
        return self._works.open_work_dir(work_id)

    def open_work_log(self, work_id: str) -> dict[str, Any]:
        return self._works.open_work_log(work_id)

    def rerender_work(self, work_id: str) -> dict[str, Any]:
        return self._works.rerender_work(work_id)

    def update_work_segments(self, work_id: str, segments: Any) -> dict[str, Any]:
        return self._works.update_work_segments(work_id, segments)


def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    ffmpeg_path = str(settings.get("ffmpeg_path", "") or "") or shutil.which("ffmpeg") or ""
    stem_preparer = StemPreparer(config.WORKS_DIR, ffmpeg_path)
    model_repo = ListRepository(config.MODELS_DB)
    runtime = RuntimeService(settings)
    uvr_tool = UvrTool(settings.get("uvr_python", "") or "", settings.get("uvr_model_dir", "") or "")
    registry = EngineRegistry([RvcEngine(settings), SvcEngine(settings)])
    return Api(
        settings,
        runtime,
        ModelService(model_repo, config.MODELS_DIR),
        stem_preparer,
        WorkService(
            ListRepository(config.WORKS_DB),
            stem_preparer,
            model_repo,
            runtime,
            InferenceRunner(settings, registry),
            uvr_tool,
        ),
    )

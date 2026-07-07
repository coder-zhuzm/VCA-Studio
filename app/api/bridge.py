"""pywebview JavaScript API bridge."""

from __future__ import annotations

from typing import Any

import config
from application.model_service import ModelService
from application.runtime_service import RuntimeService
from application.stem_preparer import StemPreparer
from infrastructure.storage import ListRepository, SettingsStore


class Api:
    def __init__(
        self,
        settings: SettingsStore,
        runtime: RuntimeService,
        models: ModelService,
        stem_preparer: StemPreparer,
    ) -> None:
        self._settings = settings
        self._runtime = runtime
        self._models = models
        self._stem_preparer = stem_preparer
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

    def get_runtime_status(self) -> dict[str, Any]:
        return self._runtime.status()

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

    def prepare_stems(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._stem_preparer.prepare(payload or {})


def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    return Api(
        settings,
        RuntimeService(settings),
        ModelService(ListRepository(config.MODELS_DB), config.MODELS_DIR),
        StemPreparer(config.WORKS_DIR),
    )

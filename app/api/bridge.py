"""pywebview JavaScript API bridge."""

from __future__ import annotations

from typing import Any

import config
from application.runtime_service import RuntimeService
from infrastructure.storage import SettingsStore


class Api:
    def __init__(self, settings: SettingsStore, runtime: RuntimeService) -> None:
        self._settings = settings
        self._runtime = runtime
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

    def check_runtime_component(self, key: str) -> dict[str, Any]:
        return self._runtime.check_component(key)


def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    return Api(settings, RuntimeService(settings))

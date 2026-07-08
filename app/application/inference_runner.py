"""Multi-framework inference dispatcher.

Picks the engine registered for a model's `framework` and runs it. Keeps the
`run_rvc` method name so existing callers and tests stay compatible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.engine import EngineRegistry
from infrastructure.storage import SettingsStore


class InferenceRunner:
    def __init__(self, settings: SettingsStore, registry: EngineRegistry) -> None:
        self._settings = settings
        self._registry = registry

    def run_rvc(self, work: dict[str, Any], model: dict[str, Any], vocals_path: str, out_path: str | None = None) -> dict[str, Any]:
        framework = str((model or {}).get("framework") or "rvc")
        engine = self._registry.get(framework)
        if not engine:
            return {"ok": False, "error": f"未知推理框架: {framework}"}
        if not engine.available():
            return {"ok": False, "error": f"{framework} 推理环境未就绪。"}

        work_dir = Path(str(work.get("work_dir") or ""))
        target = Path(out_path) if out_path else work_dir / "inference" / "ai_vocal.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        log_path = str(work.get("log_path") or work_dir / "run.log")
        return engine.infer(model, vocals_path, str(target), work.get("params") or {}, log_path)

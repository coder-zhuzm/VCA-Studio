"""Inference engine protocol and registry for multi-framework routing."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InferenceEngine(Protocol):
    framework: str

    def available(self) -> bool:
        ...

    def infer(
        self,
        model: dict[str, Any],
        vocals_path: str,
        out_path: str,
        params: dict[str, Any],
        log_path: str,
    ) -> dict[str, Any]:
        ...


class EngineRegistry:
    def __init__(self, engines: list[InferenceEngine]) -> None:
        self._engines = {engine.framework: engine for engine in engines}

    def get(self, framework: str) -> InferenceEngine | None:
        return self._engines.get(str(framework or "").strip())

    def available(self, framework: str) -> bool:
        engine = self.get(framework)
        return bool(engine and engine.available())

    def frameworks(self) -> list[str]:
        return list(self._engines)

# StemPreparer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend-only `StemPreparer` slice that validates `song` / `vocals` / `stems` audio inputs and copies them into stable role-based files under a generated work directory.

**Architecture:** `StemPreparer` is an independent application service that receives pywebview-friendly dictionaries, performs shallow stdlib validation, copies files into `config.WORKS_DIR`, and returns normalized role-to-path metadata. The pywebview bridge exposes one method, `prepare_stems(payload)`, while frontend UI and persistent work records remain deferred.

**Tech Stack:** Python 3.10+ stdlib, pywebview bridge dictionaries, existing `app/config.py` data directory conventions.

## Global Constraints

- Backend-only slice; do not modify `/create` or other frontend files.
- Use Python stdlib only: `pathlib`, `shutil`, `uuid`, and existing imports.
- Supported modes are exactly `song`, `vocals`, and `stems`.
- Do not call UVR, run inference, decode audio, inspect codecs, or whitelist extensions.
- Do not add WorkService queue, retry, logs, or persisted work records.
- Work IDs use format `work_<12 hex chars>`.
- Prepared files live under `<VCA_DATA_DIR>/works/<work_id>/input/`.
- Stable output roles are exactly `input_song`, `vocals`, and `instrumental`.
- Source extensions are preserved and lowercased.
- On validation or copy failure, return `{ "ok": false, "error": "..." }`; on copy failure, remove the newly created work directory.
- Bridge method is exactly `prepare_stems(payload)`.

---

## File Structure

- Create `app/application/stem_preparer.py` — validates mode-specific input paths, creates work directories, copies files to stable role filenames, and returns normalized metadata.
- Modify `app/config.py` — add `WORKS_DIR = DATA_DIR / "works"` and ensure it is created by `ensure_data_dirs()`.
- Modify `app/api/bridge.py` — inject `StemPreparer` and expose `prepare_stems(payload)` through pywebview.

---

### Task 1: StemPreparer service and works directory config

**Files:**
- Create: `app/application/stem_preparer.py`
- Modify: `app/config.py`

**Interfaces:**
- Consumes: `config.WORKS_DIR: pathlib.Path` added in this task.
- Produces: `StemPreparer.__init__(works_dir: Path) -> None`.
- Produces: `StemPreparer.prepare(payload: dict[str, Any]) -> dict[str, Any]`.
- Produces success response: `{"ok": True, "work_id": str, "mode": str, "files": dict[str, str]}`.
- Produces failure response: `{"ok": False, "error": str}`.

- [ ] **Step 1: Write the service smoke script before implementation**

Run this command from the repository root:

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path

from app.application.stem_preparer import StemPreparer

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    source = root / 'voice.WAV'
    source.write_text('fake audio', encoding='utf-8')
    service = StemPreparer(root / 'works')
    result = service.prepare({'mode': 'vocals', 'vocals_path': str(source)})
    assert result['ok'] is True, result
    assert result['mode'] == 'vocals', result
    copied = Path(result['files']['vocals'])
    assert copied.name == 'vocals.wav', result
    assert copied.read_text(encoding='utf-8') == 'fake audio'
    assert copied.parent.name == 'input'
    assert copied.parent.parent.name.startswith('work_')
print('stem preparer smoke ok')
PY
```

Expected before implementation: FAIL with `ModuleNotFoundError: No module named 'app.application.stem_preparer'`.

- [ ] **Step 2: Add works directory config**

In `app/config.py`, change the data-path section from:

```python
DATA_DIR = _default_data_dir()
SETTINGS_DB = DATA_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"
MODELS_DB = DATA_DIR / "models.json"
```

to:

```python
DATA_DIR = _default_data_dir()
SETTINGS_DB = DATA_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"
MODELS_DB = DATA_DIR / "models.json"
WORKS_DIR = DATA_DIR / "works"
```

Then change `ensure_data_dirs()` from:

```python
def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
```

to:

```python
def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    WORKS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: Create StemPreparer implementation**

Create `app/application/stem_preparer.py` with exactly this content:

```python
"""Lightweight input preparation for vocal conversion works."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

_MODE_REQUIREMENTS = {
    "song": (("song_path", "input_song"),),
    "vocals": (("vocals_path", "vocals"),),
    "stems": (("vocals_path", "vocals"), ("instrumental_path", "instrumental")),
}


class StemPreparer:
    def __init__(self, works_dir: Path) -> None:
        self._works_dir = works_dir
        self._works_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload or {}
        mode = str(payload.get("mode") or "").strip()
        requirements = _MODE_REQUIREMENTS.get(mode)
        if not requirements:
            return {"ok": False, "error": "不支持的输入模式。"}

        sources: list[tuple[Path, str]] = []
        for field, role in requirements:
            raw = str(payload.get(field) or "").strip()
            if not raw:
                return {"ok": False, "error": f"缺少必填文件: {field}"}
            source = Path(raw).expanduser()
            if not source.is_file():
                return {"ok": False, "error": f"文件不存在: {raw}"}
            sources.append((source, role))

        work_id = f"work_{uuid.uuid4().hex[:12]}"
        work_dir = self._works_dir / work_id
        input_dir = work_dir / "input"
        try:
            input_dir.mkdir(parents=True, exist_ok=False)
            files = self._copy_sources(sources, input_dir)
        except OSError as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "work_id": work_id, "mode": mode, "files": files}

    def _copy_sources(self, sources: list[tuple[Path, str]], input_dir: Path) -> dict[str, str]:
        files: dict[str, str] = {}
        for source, role in sources:
            target = input_dir / f"{role}{source.suffix.lower()}"
            shutil.copy2(source, target)
            files[role] = str(target)
        return files
```

- [ ] **Step 4: Run service smoke script and verify it passes**

Run:

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path

from app.application.stem_preparer import StemPreparer

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    source = root / 'voice.WAV'
    source.write_text('fake audio', encoding='utf-8')
    service = StemPreparer(root / 'works')
    result = service.prepare({'mode': 'vocals', 'vocals_path': str(source)})
    assert result['ok'] is True, result
    assert result['mode'] == 'vocals', result
    copied = Path(result['files']['vocals'])
    assert copied.name == 'vocals.wav', result
    assert copied.read_text(encoding='utf-8') == 'fake audio'
    assert copied.parent.name == 'input'
    assert copied.parent.parent.name.startswith('work_')
print('stem preparer smoke ok')
PY
```

Expected output:

```text
stem preparer smoke ok
```

- [ ] **Step 5: Run mode and error verification**

Run:

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path

from app.application.stem_preparer import StemPreparer

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    song = root / 'song.MP3'
    vocals = root / 'vocals.WAV'
    instrumental = root / 'instrumental.FLAC'
    song.write_text('song', encoding='utf-8')
    vocals.write_text('vocals', encoding='utf-8')
    instrumental.write_text('instrumental', encoding='utf-8')

    service = StemPreparer(root / 'works')

    song_result = service.prepare({'mode': 'song', 'song_path': str(song)})
    assert song_result['ok'] is True, song_result
    assert Path(song_result['files']['input_song']).name == 'input_song.mp3', song_result

    vocals_result = service.prepare({'mode': 'vocals', 'vocals_path': str(vocals)})
    assert vocals_result['ok'] is True, vocals_result
    assert Path(vocals_result['files']['vocals']).name == 'vocals.wav', vocals_result

    stems_result = service.prepare({
        'mode': 'stems',
        'vocals_path': str(vocals),
        'instrumental_path': str(instrumental),
    })
    assert stems_result['ok'] is True, stems_result
    assert Path(stems_result['files']['vocals']).name == 'vocals.wav', stems_result
    assert Path(stems_result['files']['instrumental']).name == 'instrumental.flac', stems_result

    invalid = service.prepare({'mode': 'bad'})
    assert invalid == {'ok': False, 'error': '不支持的输入模式。'}, invalid

    missing_required = service.prepare({'mode': 'song'})
    assert missing_required == {'ok': False, 'error': '缺少必填文件: song_path'}, missing_required

    missing_file = service.prepare({'mode': 'vocals', 'vocals_path': str(root / 'none.wav')})
    assert missing_file['ok'] is False, missing_file
    assert missing_file['error'].startswith('文件不存在: '), missing_file

print('stem preparer modes ok')
PY
```

Expected output:

```text
stem preparer modes ok
```

- [ ] **Step 6: Run backend compile check**

Run:

```bash
python3 -m py_compile app/config.py app/application/stem_preparer.py
```

Expected: command exits 0 with no output.

- [ ] **Step 7: Commit service and config**

Run:

```bash
git add app/config.py app/application/stem_preparer.py
git commit -m "feat: add stem preparer service

问题描述: P0 创建流程缺少将用户音频输入标准化到 work 目录的后端能力。
修复思路: 增加 StemPreparer，支持 song/vocals/stems 三种模式的路径校验与角色化复制，并创建 works 数据目录。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Bridge API and end-to-end backend verification

**Files:**
- Modify: `app/api/bridge.py`

**Interfaces:**
- Consumes: `StemPreparer.__init__(works_dir: Path) -> None` from Task 1.
- Consumes: `StemPreparer.prepare(payload: dict[str, Any]) -> dict[str, Any]` from Task 1.
- Consumes: `config.WORKS_DIR: pathlib.Path` from Task 1.
- Produces: `Api.prepare_stems(payload: dict[str, Any]) -> dict[str, Any]`.
- Produces: `build_api()` wiring that passes `config.WORKS_DIR` to `StemPreparer`.

- [ ] **Step 1: Write bridge smoke check before wiring**

Run:

```bash
VCA_DATA_DIR=$(mktemp -d) python3 - <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, 'app')
from api.bridge import build_api

source = Path('/tmp/vca_stem_bridge_source.wav')
source.write_text('bridge audio', encoding='utf-8')
api = build_api()
result = api.prepare_stems({'mode': 'vocals', 'vocals_path': str(source)})
assert result['ok'] is True, result
assert Path(result['files']['vocals']).is_file(), result
assert Path(result['files']['vocals']).read_text(encoding='utf-8') == 'bridge audio'
print('stem bridge smoke ok')
PY
```

Expected before wiring: FAIL with `AttributeError: 'Api' object has no attribute 'prepare_stems'`.

- [ ] **Step 2: Import StemPreparer in bridge**

In `app/api/bridge.py`, change the imports from:

```python
from application.model_service import ModelService
from application.runtime_service import RuntimeService
from infrastructure.storage import ListRepository, SettingsStore
```

to:

```python
from application.model_service import ModelService
from application.runtime_service import RuntimeService
from application.stem_preparer import StemPreparer
from infrastructure.storage import ListRepository, SettingsStore
```

- [ ] **Step 3: Inject StemPreparer into Api**

Change `Api.__init__` from:

```python
class Api:
    def __init__(self, settings: SettingsStore, runtime: RuntimeService, models: ModelService) -> None:
        self._settings = settings
        self._runtime = runtime
        self._models = models
        self._window = None
```

to:

```python
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
```

- [ ] **Step 4: Add bridge method**

In `app/api/bridge.py`, add this method inside `class Api`, after `set_default_model()`:

```python
    def prepare_stems(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._stem_preparer.prepare(payload or {})
```

After the edit, the end of `class Api` should contain:

```python
    def set_default_model(self, model_id: str) -> dict[str, Any]:
        return self._models.set_default_model(model_id)

    def prepare_stems(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._stem_preparer.prepare(payload or {})
```

- [ ] **Step 5: Wire StemPreparer in build_api**

Change `build_api()` from:

```python
def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    return Api(
        settings,
        RuntimeService(settings),
        ModelService(ListRepository(config.MODELS_DB), config.MODELS_DIR),
    )
```

to:

```python
def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    return Api(
        settings,
        RuntimeService(settings),
        ModelService(ListRepository(config.MODELS_DB), config.MODELS_DIR),
        StemPreparer(config.WORKS_DIR),
    )
```

- [ ] **Step 6: Run bridge smoke check and verify it passes**

Run:

```bash
VCA_DATA_DIR=$(mktemp -d) python3 - <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, 'app')
from api.bridge import build_api

source = Path('/tmp/vca_stem_bridge_source.wav')
source.write_text('bridge audio', encoding='utf-8')
api = build_api()
result = api.prepare_stems({'mode': 'vocals', 'vocals_path': str(source)})
assert result['ok'] is True, result
assert Path(result['files']['vocals']).is_file(), result
assert Path(result['files']['vocals']).read_text(encoding='utf-8') == 'bridge audio'
print('stem bridge smoke ok')
PY
```

Expected output:

```text
stem bridge smoke ok
```

- [ ] **Step 7: Run full backend verification**

Run:

```bash
python3 -m py_compile app/config.py app/main.py app/api/bridge.py app/infrastructure/storage.py app/application/runtime_service.py app/application/model_service.py app/application/stem_preparer.py
VCA_DATA_DIR=$(mktemp -d) python3 - <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, 'app')
from api.bridge import build_api

source_dir = Path('/tmp/vca_stem_full_verify')
source_dir.mkdir(parents=True, exist_ok=True)
song = source_dir / 'song.MP3'
vocals = source_dir / 'vocals.WAV'
instrumental = source_dir / 'instrumental.FLAC'
song.write_text('song', encoding='utf-8')
vocals.write_text('vocals', encoding='utf-8')
instrumental.write_text('instrumental', encoding='utf-8')

api = build_api()
status = api.get_runtime_status()
assert 'components' in status, status
assert len(status['components']) == 5, status
assert api.set_runtime_path('ffmpeg_path', '')['ok'] is True
assert api.set_runtime_path('bad_key', 'x')['ok'] is False

song_result = api.prepare_stems({'mode': 'song', 'song_path': str(song)})
assert song_result['ok'] is True, song_result
assert Path(song_result['files']['input_song']).name == 'input_song.mp3', song_result

vocals_result = api.prepare_stems({'mode': 'vocals', 'vocals_path': str(vocals)})
assert vocals_result['ok'] is True, vocals_result
assert Path(vocals_result['files']['vocals']).name == 'vocals.wav', vocals_result

stems_result = api.prepare_stems({
    'mode': 'stems',
    'vocals_path': str(vocals),
    'instrumental_path': str(instrumental),
})
assert stems_result['ok'] is True, stems_result
assert Path(stems_result['files']['vocals']).name == 'vocals.wav', stems_result
assert Path(stems_result['files']['instrumental']).name == 'instrumental.flac', stems_result

invalid = api.prepare_stems({'mode': 'bad'})
assert invalid == {'ok': False, 'error': '不支持的输入模式。'}, invalid
missing = api.prepare_stems({'mode': 'song'})
assert missing == {'ok': False, 'error': '缺少必填文件: song_path'}, missing
print('stem backend verification ok')
PY
```

Expected output includes:

```text
stem backend verification ok
```

and both commands exit 0.

- [ ] **Step 8: Confirm no frontend build is required for this task**

Run:

```bash
git diff --name-only HEAD --
```

Expected changed files are backend-only:

```text
app/api/bridge.py
```

If frontend files appear, stop and remove those changes or run `npm run build --prefix web` before committing.

- [ ] **Step 9: Commit bridge wiring**

Run:

```bash
git add app/api/bridge.py
git commit -m "feat: expose stem preparation bridge

问题描述: 桌面 bridge 尚未暴露轻量音频输入准备能力。
修复思路: 将 StemPreparer 注入 Api，并新增 prepare_stems(payload) 方法，供后续 Create/WorkService 流程调用。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

- Spec coverage: Task 1 implements `StemPreparer`, file roles, validation, copy behavior, work directory layout, cleanup on copy failure, and config. Task 2 implements bridge method and end-to-end backend verification. Frontend and WorkService remain deferred as specified.
- Placeholder scan: no TBD/TODO/fill-in placeholders; code and commands are explicit.
- Type consistency: plan consistently uses `StemPreparer.prepare(payload: dict[str, Any])`, `config.WORKS_DIR`, `Api.prepare_stems(payload)`, and roles `input_song`, `vocals`, `instrumental`.

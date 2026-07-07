# WorkService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend-only `WorkService` slice that creates persisted work records from prepared inputs and exposes create/list/get APIs through the pywebview bridge.

**Architecture:** `WorkService` wraps the existing `StemPreparer` and `ListRepository`: it prepares inputs first, then writes metadata to `WORKS_DB`. The bridge remains a thin forwarding layer; frontend API wrappers and pages are intentionally untouched.

**Tech Stack:** Python 3.10+ stdlib, existing pywebview bridge dictionaries, existing `ListRepository`, existing `StemPreparer`, JSON metadata under `VCA_DATA_DIR`.

## Global Constraints

- Backend-only slice; do not modify frontend files under `web/`.
- Keep existing `bridge.prepare_stems(payload)` available.
- Add bridge methods exactly: `create_work(payload)`, `list_works()`, `get_work(work_id)`.
- Add config constant exactly: `WORKS_DB = DATA_DIR / "works.json"`.
- Reuse `infrastructure.storage.ListRepository`; do not introduce a database.
- Reuse `StemPreparer`; do not duplicate input validation/copy logic in `WorkService`.
- Do not add async queues, threads, workers, JobRunner, UVR, inference, mixing, or export.
- Supported input modes remain exactly `song`, `vocals`, and `stems`.
- Work records include at least: `id`, `name`, `input_mode`, `input_files`, `status`, `stage`, `logs`, `created_at`, `updated_at`.
- First-version statuses are only `pending` and `failed`; successful creation uses `status="pending"` and `stage="prepared"`.
- If `StemPreparer` fails, `create_work` returns `ok=false` and does not write a work record.
- Use pywebview-friendly dictionaries/lists and user-facing `{ "ok": false, "error": "..." }` failures.

---

## File Structure

- Create `app/application/work_service.py` — application service that prepares input through `StemPreparer`, maps prepared files into a work record, persists it with `ListRepository`, and exposes list/get helpers.
- Modify `app/config.py` — add `WORKS_DB` next to existing JSON metadata paths.
- Modify `app/api/bridge.py` — inject `WorkService` and expose `create_work`, `list_works`, and `get_work` while keeping `prepare_stems`.
- No frontend files are changed.

---

### Task 1: Add WorkService and WORKS_DB config

**Files:**
- Create: `app/application/work_service.py`
- Modify: `app/config.py`

**Interfaces:**
- Consumes: `StemPreparer.prepare(payload: dict[str, Any]) -> dict[str, Any]`.
- Consumes: `ListRepository.add(item: dict[str, Any]) -> dict[str, Any]`.
- Consumes: `ListRepository.all() -> list[dict[str, Any]]`.
- Consumes: `ListRepository.get(item_id: str) -> dict[str, Any] | None`.
- Produces: `WORKS_DB = DATA_DIR / "works.json"`.
- Produces: `WorkService.__init__(repo: ListRepository, stem_preparer: StemPreparer) -> None`.
- Produces: `WorkService.create_work(payload: dict[str, Any]) -> dict[str, Any]`.
- Produces: `WorkService.list_works() -> dict[str, Any]`.
- Produces: `WorkService.get_work(work_id: str) -> dict[str, Any]`.

- [x] **Step 1: Write failing smoke for successful work creation**

Run from repo root:

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path

from app.application.stem_preparer import StemPreparer
from app.application.work_service import WorkService
from app.infrastructure.storage import ListRepository

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    song = root / 'song.WAV'
    song.write_text('fake audio', encoding='utf-8')

    service = WorkService(
        ListRepository(root / 'works.json'),
        StemPreparer(root / 'works'),
    )
    result = service.create_work({'name': 'Demo', 'mode': 'song', 'song_path': str(song)})

    assert result['ok'] is True, result
    work = result['work']
    assert work['id'].startswith('work_'), work
    assert work['name'] == 'Demo', work
    assert work['input_mode'] == 'song', work
    assert work['status'] == 'pending', work
    assert work['stage'] == 'prepared', work
    assert len(work['input_files']) == 1, work
    assert work['input_files'][0]['role'] == 'input_song', work
    assert Path(work['input_files'][0]['stored_path']).is_file(), work
    assert work['logs'][0]['message'] == 'Input prepared', work
    assert service.list_works()['works'][0]['id'] == work['id']
    assert service.get_work(work['id'])['work']['id'] == work['id']
print('work service create smoke ok')
PY
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'app.application.work_service'
```

- [x] **Step 2: Add WORKS_DB config**

In `app/config.py`, change:

```python
DATA_DIR = _default_data_dir()
SETTINGS_DB = DATA_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"
MODELS_DB = DATA_DIR / "models.json"
WORKS_DIR = DATA_DIR / "works"
```

to:

```python
DATA_DIR = _default_data_dir()
SETTINGS_DB = DATA_DIR / "settings.json"
MODELS_DIR = DATA_DIR / "models"
MODELS_DB = DATA_DIR / "models.json"
WORKS_DIR = DATA_DIR / "works"
WORKS_DB = DATA_DIR / "works.json"
```

- [x] **Step 3: Create WorkService implementation**

Create `app/application/work_service.py`:

```python
"""Work metadata creation and lookup service."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.stem_preparer import StemPreparer
from infrastructure.storage import ListRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkService:
    def __init__(self, repo: ListRepository, stem_preparer: StemPreparer) -> None:
        self._repo = repo
        self._stem_preparer = stem_preparer

    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload or {}
        prepared = self._stem_preparer.prepare(payload)
        if not prepared.get("ok"):
            return {"ok": False, "error": str(prepared.get("error") or "输入准备失败。")}

        created_at = _now()
        record = {
            "id": str(prepared["work_id"]),
            "name": str(payload.get("name") or "").strip() or "Untitled Work",
            "input_mode": str(prepared["mode"]),
            "input_files": self._input_files(prepared.get("files") or {}, payload),
            "status": "pending",
            "stage": "prepared",
            "logs": [
                {
                    "level": "info",
                    "message": "Input prepared",
                    "created_at": created_at,
                }
            ],
            "created_at": created_at,
            "updated_at": created_at,
        }

        try:
            self._repo.add(record)
        except OSError as exc:
            self._cleanup_work_dir(record)
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "work": record}

    def list_works(self) -> dict[str, Any]:
        return {"ok": True, "works": self._repo.all()}

    def get_work(self, work_id: str) -> dict[str, Any]:
        work = self._repo.get(str(work_id))
        if not work:
            return {"ok": False, "error": "Work not found"}
        return {"ok": True, "work": work}

    def _input_files(self, files: dict[str, str], payload: dict[str, Any]) -> list[dict[str, str]]:
        sources = {
            "input_song": str(payload.get("song_path") or "").strip(),
            "vocals": str(payload.get("vocals_path") or "").strip(),
            "instrumental": str(payload.get("instrumental_path") or "").strip(),
        }
        result: list[dict[str, str]] = []
        for role, stored_path in files.items():
            result.append(
                {
                    "role": role,
                    "source_path": sources.get(role, ""),
                    "stored_path": str(stored_path),
                    "filename": Path(str(stored_path)).name,
                }
            )
        return result

    def _cleanup_work_dir(self, record: dict[str, Any]) -> None:
        files = record.get("input_files") or []
        first = next((item.get("stored_path") for item in files if item.get("stored_path")), "")
        if first:
            shutil.rmtree(Path(str(first)).parent.parent, ignore_errors=True)
```

- [x] **Step 4: Run successful creation smoke and verify it passes**

Run:

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path

from app.application.stem_preparer import StemPreparer
from app.application.work_service import WorkService
from app.infrastructure.storage import ListRepository

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    song = root / 'song.WAV'
    song.write_text('fake audio', encoding='utf-8')

    service = WorkService(
        ListRepository(root / 'works.json'),
        StemPreparer(root / 'works'),
    )
    result = service.create_work({'name': 'Demo', 'mode': 'song', 'song_path': str(song)})

    assert result['ok'] is True, result
    work = result['work']
    assert work['id'].startswith('work_'), work
    assert work['name'] == 'Demo', work
    assert work['input_mode'] == 'song', work
    assert work['status'] == 'pending', work
    assert work['stage'] == 'prepared', work
    assert len(work['input_files']) == 1, work
    assert work['input_files'][0]['role'] == 'input_song', work
    assert Path(work['input_files'][0]['stored_path']).is_file(), work
    assert work['logs'][0]['message'] == 'Input prepared', work
    assert service.list_works()['works'][0]['id'] == work['id']
    assert service.get_work(work['id'])['work']['id'] == work['id']
print('work service create smoke ok')
PY
```

Expected output:

```text
work service create smoke ok
```

- [x] **Step 5: Run failure and default-name smoke**

Run:

```bash
python3 - <<'PY'
import tempfile
from pathlib import Path

from app.application.stem_preparer import StemPreparer
from app.application.work_service import WorkService
from app.infrastructure.storage import ListRepository

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    vocals = root / 'vocals.wav'
    instrumental = root / 'inst.flac'
    vocals.write_text('vocals', encoding='utf-8')
    instrumental.write_text('inst', encoding='utf-8')

    service = WorkService(ListRepository(root / 'works.json'), StemPreparer(root / 'works'))

    missing = service.create_work({'mode': 'song', 'song_path': str(root / 'missing.wav')})
    assert missing['ok'] is False, missing
    assert service.list_works() == {'ok': True, 'works': []}, service.list_works()

    stems = service.create_work({
        'mode': 'stems',
        'vocals_path': str(vocals),
        'instrumental_path': str(instrumental),
    })
    assert stems['ok'] is True, stems
    work = stems['work']
    assert work['name'] == 'Untitled Work', work
    assert work['input_mode'] == 'stems', work
    assert [item['role'] for item in work['input_files']] == ['vocals', 'instrumental'], work
    assert service.get_work('missing') == {'ok': False, 'error': 'Work not found'}
print('work service failure smoke ok')
PY
```

Expected output:

```text
work service failure smoke ok
```

- [x] **Step 6: Commit Task 1**

Run:

```bash
git add app/config.py app/application/work_service.py
git commit -m "feat: add WorkService metadata persistence

问题描述: 需要在 StemPreparer 之后创建可查询、可持久化的 work metadata。
修复思路: 新增 WorkService，复用 StemPreparer 准备输入并通过 ListRepository 写入 works.json。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 2: Expose WorkService through bridge

**Files:**
- Modify: `app/api/bridge.py`

**Interfaces:**
- Consumes: `WorkService.create_work(payload: dict[str, Any]) -> dict[str, Any]`.
- Consumes: `WorkService.list_works() -> dict[str, Any]`.
- Consumes: `WorkService.get_work(work_id: str) -> dict[str, Any]`.
- Produces bridge method: `Api.create_work(payload: dict[str, Any]) -> dict[str, Any]`.
- Produces bridge method: `Api.list_works() -> dict[str, Any]`.
- Produces bridge method: `Api.get_work(work_id: str) -> dict[str, Any]`.
- Preserves bridge method: `Api.prepare_stems(payload: dict[str, Any]) -> dict[str, Any]`.

- [x] **Step 1: Write failing bridge smoke**

Run:

```bash
VCA_DATA_DIR="$(mktemp -d)" python3 - <<'PY'
from pathlib import Path

from app.api.bridge import build_api

api = build_api()
source = Path(api.get_app_status()['data_dir']) / 'bridge-song.wav'
source.write_text('fake audio', encoding='utf-8')

result = api.create_work({'name': 'Bridge Demo', 'mode': 'song', 'song_path': str(source)})
assert result['ok'] is True, result
work = result['work']
assert api.list_works()['works'][0]['id'] == work['id']
assert api.get_work(work['id'])['work']['name'] == 'Bridge Demo'
assert api.prepare_stems({'mode': 'song', 'song_path': str(source)})['ok'] is True
print('bridge work service smoke ok')
PY
```

Expected before bridge change:

```text
AttributeError: 'Api' object has no attribute 'create_work'
```

- [x] **Step 2: Update imports**

In `app/api/bridge.py`, change imports from:

```python
from application.model_service import ModelService
from application.runtime_service import RuntimeService
from application.stem_preparer import StemPreparer
from infrastructure.storage import ListRepository, SettingsStore
```

to:

```python
from application.model_service import ModelService
from application.runtime_service import RuntimeService
from application.stem_preparer import StemPreparer
from application.work_service import WorkService
from infrastructure.storage import ListRepository, SettingsStore
```

- [x] **Step 3: Inject WorkService into Api**

Change `Api.__init__` from:

```python
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

to:

```python
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
```

- [x] **Step 4: Add bridge forwarding methods**

After existing `prepare_stems`, add:

```python
    def create_work(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._works.create_work(payload or {})

    def list_works(self) -> dict[str, Any]:
        return self._works.list_works()

    def get_work(self, work_id: str) -> dict[str, Any]:
        return self._works.get_work(work_id)
```

- [x] **Step 5: Update build_api construction**

Change `build_api()` from:

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

to:

```python
def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    stem_preparer = StemPreparer(config.WORKS_DIR)
    return Api(
        settings,
        RuntimeService(settings),
        ModelService(ListRepository(config.MODELS_DB), config.MODELS_DIR),
        stem_preparer,
        WorkService(ListRepository(config.WORKS_DB), stem_preparer),
    )
```

- [x] **Step 6: Run bridge smoke and verify it passes**

Run:

```bash
VCA_DATA_DIR="$(mktemp -d)" python3 - <<'PY'
from pathlib import Path

from app.api.bridge import build_api

api = build_api()
source = Path(api.get_app_status()['data_dir']) / 'bridge-song.wav'
source.write_text('fake audio', encoding='utf-8')

result = api.create_work({'name': 'Bridge Demo', 'mode': 'song', 'song_path': str(source)})
assert result['ok'] is True, result
work = result['work']
assert api.list_works()['works'][0]['id'] == work['id']
assert api.get_work(work['id'])['work']['name'] == 'Bridge Demo'
assert api.prepare_stems({'mode': 'song', 'song_path': str(source)})['ok'] is True
print('bridge work service smoke ok')
PY
```

Expected output:

```text
bridge work service smoke ok
```

- [x] **Step 7: Commit Task 2**

Run:

```bash
git add app/api/bridge.py
git commit -m "feat: expose WorkService bridge API

问题描述: 前端宿主需要通过 pywebview 创建和查询 work 任务。
修复思路: 在 bridge 中注入 WorkService，并新增 create_work、list_works、get_work 薄封装。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 3: Final backend verification

**Files:**
- Verify: `app/application/work_service.py`
- Verify: `app/api/bridge.py`
- Verify: `app/config.py`

**Interfaces:**
- Verifies the complete backend-only WorkService flow.
- Produces no new code unless verification reveals a defect.

- [x] **Step 1: Run static compile check**

Run:

```bash
python3 -m py_compile app/application/work_service.py app/api/bridge.py app/config.py
```

Expected output: no output and exit code `0`.

- [x] **Step 2: Run full backend smoke**

Run:

```bash
VCA_DATA_DIR="$(mktemp -d)" python3 - <<'PY'
import json
from pathlib import Path

from app.api.bridge import build_api

api = build_api()
data_dir = Path(api.get_app_status()['data_dir'])
song = data_dir / 'song.wav'
vocals = data_dir / 'vocals.wav'
instrumental = data_dir / 'instrumental.wav'
song.write_text('song', encoding='utf-8')
vocals.write_text('vocals', encoding='utf-8')
instrumental.write_text('instrumental', encoding='utf-8')

song_result = api.create_work({'name': 'Song Work', 'mode': 'song', 'song_path': str(song)})
assert song_result['ok'] is True, song_result
song_work = song_result['work']
assert song_work['status'] == 'pending', song_work
assert song_work['stage'] == 'prepared', song_work

stems_result = api.create_work({
    'mode': 'stems',
    'vocals_path': str(vocals),
    'instrumental_path': str(instrumental),
})
assert stems_result['ok'] is True, stems_result
stems_work = stems_result['work']
assert stems_work['name'] == 'Untitled Work', stems_work
assert stems_work['input_mode'] == 'stems', stems_work

missing = api.create_work({'mode': 'song', 'song_path': str(data_dir / 'missing.wav')})
assert missing['ok'] is False, missing

works = api.list_works()['works']
assert [work['id'] for work in works] == [stems_work['id'], song_work['id']], works
assert api.get_work(song_work['id'])['work']['name'] == 'Song Work'
assert api.get_work('missing') == {'ok': False, 'error': 'Work not found'}

db = data_dir / 'works.json'
assert db.is_file(), db
stored = json.loads(db.read_text(encoding='utf-8'))
assert len(stored) == 2, stored
assert all(work['status'] == 'pending' for work in stored), stored
print('full work service smoke ok')
PY
```

Expected output:

```text
full work service smoke ok
```

- [x] **Step 3: Confirm no frontend changes**

Run:

```bash
git diff --name-only HEAD~2..HEAD
```

Expected output includes only backend files from these commits:

```text
app/api/bridge.py
app/application/work_service.py
app/config.py
```

If docs commits are included in the selected range, `docs/superpowers/...` may also appear. No path under `web/` should appear.

- [x] **Step 4: Commit verification note only if fixes were needed**

If Step 1 or Step 2 failed and you changed code to fix it, commit the fix:

```bash
git add app/application/work_service.py app/api/bridge.py app/config.py
git commit -m "fix: stabilize WorkService backend flow

问题描述: WorkService 后端验证暴露创建或查询流程缺陷。
修复思路: 修正 WorkService/bridge/config 以满足 backend-only smoke 验证。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: commit succeeds if fixes were made. If no fixes were needed, skip this commit.

---

## Self-Review

- Spec coverage: covered `WORKS_DB`, `work_service.py`, `ListRepository`, bridge `create_work/list_works/get_work`, retained `prepare_stems`, required record fields, `pending/prepared`, no frontend, no async, StemPreparer failure no write, and backend verification.
- Placeholder scan: no TBD/TODO/placeholder instructions remain.
- Type consistency: `WorkService` method names and return shapes are consistent across implementation, bridge, and smoke scripts.

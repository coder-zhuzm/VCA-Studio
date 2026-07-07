# ModelService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local RVC and So-VITS-SVC model management: import, list, check, delete, and set default models from `/models`.

**Architecture:** Backend owns validation, file copying, JSON persistence, and safe deletion via `ModelService`. Bridge exposes model APIs. Frontend keeps `/models` state local, calls API wrappers, and renders an Ant Design import form/table.

**Tech Stack:** Python 3.10+ stdlib, pywebview bridge, JSON storage, React 19, TypeScript, Vite, Ant Design.

## Global Constraints

- Support both RVC and So-VITS-SVC local model import.
- RVC requires `checkpoint .pth`; optional `.index`.
- So-VITS-SVC requires `checkpoint .pth` and `config.json`; optional `diffusion .pt` and `diffusion_config .yaml / .yml`.
- Do not implement inference, ModelScope, zip extraction, drag/drop, automatic format discovery, or file picker dialogs.
- Imported files must be copied into `DATA_DIR/models/<model_id>/`; do not depend on external source paths after import.
- Add `MODELS_DIR` and `MODELS_DB` to `app/config.py`.
- Use existing JSON storage style; if `ListRepository` is missing, add the minimal version to `app/infrastructure/storage.py`.
- Bridge methods are exactly: `list_models()`, `import_model(payload)`, `delete_model(id)`, `check_model(id)`, `set_default_model(id)`.
- Frontend uses local component state only; no global store.
- Text path inputs only; no file picker.

---

## File Structure

- Modify `app/config.py` — add `MODELS_DIR` and `MODELS_DB`.
- Modify `app/infrastructure/storage.py` — add minimal `ListRepository`.
- Create `app/application/model_service.py` — model validation, copy, persistence, check, delete, default selection.
- Modify `app/api/bridge.py` — inject `ModelService` and expose model bridge methods.
- Modify `web/src/api/types.ts` — model types and DesktopApi methods.
- Modify `web/src/api/index.ts` — frontend model API wrappers and browser mock.
- Modify `web/src/pages/Models.tsx` — import form and model table.
- Modify `README.md` — update current progress with model management.

---

### Task 1: Backend ModelService

**Files:**
- Modify: `app/config.py`
- Modify: `app/infrastructure/storage.py`
- Create: `app/application/model_service.py`
- Modify: `app/api/bridge.py`

**Interfaces:**
- Produces: `config.MODELS_DIR: Path`, `config.MODELS_DB: Path`
- Produces: `ListRepository.all()`, `get(id)`, `add(item)`, `update(id, item)`, `remove(id)`
- Produces: `ModelService.list_models() -> list[dict[str, Any]]`
- Produces: `ModelService.import_model(payload: dict[str, Any]) -> dict[str, Any]`
- Produces: `ModelService.delete_model(model_id: str) -> dict[str, Any]`
- Produces: `ModelService.check_model(model_id: str) -> dict[str, Any]`
- Produces: `ModelService.set_default_model(model_id: str) -> dict[str, Any]`
- Produces bridge methods with the same names from the spec.

- [ ] **Step 1: Add model paths to config**

Update `app/config.py` after `SETTINGS_DB`:

```python
MODELS_DIR = DATA_DIR / "models"
MODELS_DB = DATA_DIR / "models.json"
```

Update `ensure_data_dirs()`:

```python
def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Add ListRepository**

Append to `app/infrastructure/storage.py`:

```python
class ListRepository:
    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path, [])
        self._lock = threading.RLock()

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._store.read()
            return data if isinstance(data, list) else []

    def get(self, item_id: str) -> dict[str, Any] | None:
        return next((item for item in self.all() if item.get("id") == item_id), None)

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            items = self.all()
            items.insert(0, item)
            self._store.write(items)
            return item

    def update(self, item_id: str, item: dict[str, Any]) -> None:
        with self._lock:
            items = self.all()
            for index, current in enumerate(items):
                if current.get("id") == item_id:
                    items[index] = item
                    self._store.write(items)
                    return

    def replace_all(self, items: list[dict[str, Any]]) -> None:
        with self._lock:
            self._store.write(items)

    def remove(self, item_id: str) -> None:
        with self._lock:
            self._store.write([item for item in self.all() if item.get("id") != item_id])
```

- [ ] **Step 3: Create ModelService**

Create `app/application/model_service.py` with these responsibilities:

```python
"""Local voice model import and metadata management."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
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
        framework = str((payload or {}).get("framework") or "").strip()
        if framework not in FRAMEWORKS:
            return {"ok": False, "error": "不支持的模型框架。"}
        name = str((payload or {}).get("name") or "").strip() or framework
        error = self._validate_payload(framework, payload or {})
        if error:
            return {"ok": False, "error": error}

        model_id = f"model_{uuid.uuid4().hex[:12]}"
        model_dir = self._models_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        try:
            files = self._copy_files(payload or {}, model_dir)
            first = len(self._repo.all()) == 0
            record = {
                "id": model_id,
                "name": name,
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
        self._repo.update(model["id"], updated)
        return {"ok": True, "model": updated}

    def set_default_model(self, model_id: str) -> dict[str, Any]:
        if not self._repo.get(str(model_id)):
            return {"ok": False, "error": "模型不存在。"}
        items = []
        for model in self._repo.all():
            items.append({**model, "is_default": model.get("id") == model_id, "updated_at": _now()})
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
            if role == "config":
                name = "config.json"
            else:
                name = f"{role}{src.suffix.lower()}"
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
```

- [ ] **Step 4: Wire bridge methods**

Modify `app/api/bridge.py`:

```python
from application.model_service import ModelService
from infrastructure.storage import ListRepository, SettingsStore
```

Change constructor:

```python
class Api:
    def __init__(self, settings: SettingsStore, runtime: RuntimeService, models: ModelService) -> None:
        self._settings = settings
        self._runtime = runtime
        self._models = models
        self._window = None
```

Add methods:

```python
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
```

Update `build_api()`:

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

- [ ] **Step 5: Backend smoke**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
python3 -m py_compile app/config.py app/api/bridge.py app/application/model_service.py app/infrastructure/storage.py
VCA_DATA_DIR=$(mktemp -d) python3 - <<'PY'
from pathlib import Path
import sys, tempfile
sys.path.insert(0, 'app')
from api.bridge import build_api
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    rvc = root / 'rvc.pth'; rvc.write_text('fake')
    idx = root / 'rvc.index'; idx.write_text('fake')
    svc = root / 'svc.pth'; svc.write_text('fake')
    cfg = root / 'config.json'; cfg.write_text('{}')
    api = build_api()
    assert isinstance(api.list_models(), list)
    assert api.import_model({'framework': 'bad'})['ok'] is False
    r = api.import_model({'name': 'rvc', 'framework': 'rvc', 'checkpoint_path': str(rvc), 'index_path': str(idx)})
    assert r['ok'] is True, r
    s = api.import_model({'name': 'svc', 'framework': 'so-vits-svc', 'checkpoint_path': str(svc), 'config_path': str(cfg)})
    assert s['ok'] is True, s
    assert len(api.list_models()) == 2
    assert api.set_default_model(s['model']['id'])['ok'] is True
    assert api.check_model(r['model']['id'])['model']['status'] == 'ready'
    assert api.delete_model(r['model']['id'])['ok'] is True
print('model backend smoke ok')
PY
```

Expected output includes `model backend smoke ok`.

- [ ] **Step 6: Commit backend**

```bash
git add app/config.py app/infrastructure/storage.py app/application/model_service.py app/api/bridge.py
git commit -m "feat: add local model service

问题描述: 项目缺少本地 RVC 与 So-VITS-SVC 模型导入、列表、检查、删除和默认模型能力。
修复思路: 增加 ModelService、models.json 存储、模型文件复制到数据目录，并通过 bridge 暴露模型管理 API。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Frontend model API types and wrapper

**Files:**
- Modify: `web/src/api/types.ts`
- Modify: `web/src/api/index.ts`

**Interfaces:**
- Consumes Task 1 bridge methods.
- Produces types: `ModelRecord`, `ModelCheck`, `ImportModelPayload`, `ModelMutationResult`, `ModelListResult`.
- Produces wrapper methods: `api.listModels()`, `api.importModel(payload)`, `api.deleteModel(id)`, `api.checkModel(id)`, `api.setDefaultModel(id)`.

- [ ] **Step 1: Extend types**

Append to `web/src/api/types.ts`:

```ts
export type ModelFramework = 'rvc' | 'so-vits-svc'
export type ModelStatus = 'ready' | 'missing' | 'error'

export interface ModelCheck {
  key: string
  label: string
  ok: boolean
  message: string
}

export interface ModelRecord {
  id: string
  name: string
  framework: ModelFramework
  files: Record<string, string>
  status: ModelStatus
  is_default: boolean
  created_at: string
  updated_at: string
  checks: ModelCheck[]
}

export interface ImportModelPayload {
  name: string
  framework: ModelFramework
  checkpoint_path: string
  index_path?: string
  config_path?: string
  diffusion_path?: string
  diffusion_config_path?: string
}

export interface ModelMutationResult {
  ok: boolean
  error?: string
  model?: ModelRecord
  models?: ModelRecord[]
}
```

Extend `DesktopApi`:

```ts
  list_models: () => Promise<ModelRecord[]>
  import_model: (payload: ImportModelPayload) => Promise<ModelMutationResult>
  delete_model: (id: string) => Promise<ModelMutationResult>
  check_model: (id: string) => Promise<ModelMutationResult>
  set_default_model: (id: string) => Promise<ModelMutationResult>
```

- [ ] **Step 2: Add wrapper + browser mock**

In `web/src/api/index.ts`, import the new types and add mock storage:

```ts
const mockModels: ModelRecord[] = []
```

Add mock methods to `mock`:

```ts
  async list_models(): Promise<ModelRecord[]> {
    return mockModels
  },
  async import_model(payload: ImportModelPayload): Promise<ModelMutationResult> {
    const model: ModelRecord = {
      id: `model_${Date.now()}`,
      name: payload.name || payload.framework,
      framework: payload.framework,
      files: Object.fromEntries(Object.entries(payload).filter(([key, value]) => key.endsWith('_path') && value)) as Record<string, string>,
      status: 'ready',
      is_default: mockModels.length === 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      checks: [],
    }
    mockModels.unshift(model)
    return { ok: true, model }
  },
  async delete_model(id: string): Promise<ModelMutationResult> {
    const index = mockModels.findIndex((model) => model.id === id)
    if (index >= 0) mockModels.splice(index, 1)
    return { ok: true, models: mockModels }
  },
  async check_model(id: string): Promise<ModelMutationResult> {
    const model = mockModels.find((item) => item.id === id)
    return model ? { ok: true, model } : { ok: false, error: '模型不存在。' }
  },
  async set_default_model(id: string): Promise<ModelMutationResult> {
    for (const model of mockModels) model.is_default = model.id === id
    return { ok: true, models: mockModels }
  },
```

Add API wrapper methods:

```ts
  listModels: async () => (await desktop()).list_models(),
  importModel: async (payload: ImportModelPayload) => (await desktop()).import_model(payload),
  deleteModel: async (id: string) => (await desktop()).delete_model(id),
  checkModel: async (id: string) => (await desktop()).check_model(id),
  setDefaultModel: async (id: string) => (await desktop()).set_default_model(id),
```

- [ ] **Step 3: Build**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
npm run build --prefix web
```

Expected: build exits 0.

- [ ] **Step 4: Commit frontend API**

```bash
git add web/src/api/types.ts web/src/api/index.ts
git commit -m "feat: add model frontend API wrapper

问题描述: 前端缺少模型管理的类型、桌面 API 封装和浏览器 mock。
修复思路: 增加模型记录、导入 payload、操作结果类型，并映射 list/import/delete/check/default bridge 方法。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Models page UI

**Files:**
- Modify: `web/src/pages/Models.tsx`

**Interfaces:**
- Consumes Task 2 wrapper methods.
- Produces `/models` import form and table.

- [ ] **Step 1: Replace Models page**

Implement `web/src/pages/Models.tsx` with:

- local `models` state
- `Form` with fields `name`, `framework`, `checkpoint_path`, `index_path`, `config_path`, `diffusion_path`, `diffusion_config_path`
- conditional fields based on framework
- import button calling `api.importModel`
- table columns: name, framework, status, default, files, actions
- actions: check, set default, delete via `Popconfirm`

Use the simplest Ant Design components: `Card`, `Form`, `Input`, `Select`, `Button`, `Table`, `Tag`, `Space`, `Popconfirm`, `message`, `Typography`.

- [ ] **Step 2: Required field logic**

Validation in frontend:

- `name`, `framework`, `checkpoint_path` required for all.
- `config_path` required only when framework is `so-vits-svc`.
- All other fields optional.

Backend remains final authority.

- [ ] **Step 3: Build**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
npm run build --prefix web
```

Expected: build exits 0.

- [ ] **Step 4: Commit page**

```bash
git add web/src/pages/Models.tsx
git commit -m "feat: add local model management page

问题描述: /models 页面仍是占位，无法导入或管理本地模型。
修复思路: 使用 Ant Design 表单和表格支持 RVC/So-VITS-SVC 模型导入、列表、检查、默认模型和删除操作。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: README and final verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes completed ModelService feature.
- Produces README current progress update and final verification evidence.

- [ ] **Step 1: Update README current progress**

Add model management to current progress and pages:

```markdown
- ✅ `/models` 本地模型管理第一版
- ✅ RVC / So-VITS-SVC 模型导入、检查、删除、默认模型
```

Add a short section:

```markdown
## 模型管理当前能力

`/models` 页面支持本地导入 RVC 与 So-VITS-SVC 模型。导入时会把模型文件复制到数据目录，后续流程不依赖原始外部路径。

### 支持格式

| Framework | 必填 | 可选 |
|---|---|---|
| RVC | `.pth` | `.index` |
| So-VITS-SVC | `.pth`, `config.json` | diffusion `.pt`, diffusion config `.yaml/.yml` |

当前不做推理、zip 导入、ModelScope、文件选择器和深度依赖检测。
```

- [ ] **Step 2: Full verification**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
python3 -m py_compile app/config.py app/api/bridge.py app/application/model_service.py app/infrastructure/storage.py
VCA_DATA_DIR=$(mktemp -d) python3 - <<'PY'
from pathlib import Path
import sys, tempfile
sys.path.insert(0, 'app')
from api.bridge import build_api
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    rvc = root / 'rvc.pth'; rvc.write_text('fake')
    svc = root / 'svc.pth'; svc.write_text('fake')
    cfg = root / 'config.json'; cfg.write_text('{}')
    api = build_api()
    assert isinstance(api.list_models(), list)
    assert api.import_model({'framework': 'bad'})['ok'] is False
    r = api.import_model({'name': 'rvc', 'framework': 'rvc', 'checkpoint_path': str(rvc)})
    assert r['ok'] is True, r
    s = api.import_model({'name': 'svc', 'framework': 'so-vits-svc', 'checkpoint_path': str(svc), 'config_path': str(cfg)})
    assert s['ok'] is True, s
    assert api.set_default_model(s['model']['id'])['ok'] is True
    assert api.delete_model(r['model']['id'])['ok'] is True
print('model backend smoke ok')
PY
npm run build --prefix web
```

Expected: output includes `model backend smoke ok`; npm build exits 0.

- [ ] **Step 3: Commit README**

```bash
git add README.md
git commit -m "docs: document model management slice

问题描述: README 未说明当前本地模型管理第一版的能力和限制。
修复思路: 补充 RVC/So-VITS-SVC 导入格式、文件复制策略、页面状态和当前不支持项。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

- Spec coverage: backend storage/service/bridge, frontend types/wrapper/page, README, and verification are covered.
- Deliberate deferrals preserved: no inference, ModelScope, zip extraction, drag/drop, format discovery, or file picker.
- Placeholder scan: no TBD/TODO/fill-in steps.
- Type consistency: backend `rvc | so-vits-svc`, bridge snake_case, frontend camelCase wrapper all match.

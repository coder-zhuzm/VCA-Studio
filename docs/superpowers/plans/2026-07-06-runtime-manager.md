# Runtime Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first Runtime Manager slice so users can view runtime status, save manual paths, and re-check components from `/runtime`.

**Architecture:** Backend owns detection and persistence via a small `RuntimeService` using `SettingsStore` and stdlib. The pywebview bridge exposes three runtime methods. Frontend keeps local state in `Runtime.tsx`, calls the bridge wrapper, and renders Ant Design inputs/table.

**Tech Stack:** Python 3.10+ stdlib, pywebview bridge, JSON settings, React 19, TypeScript, Vite, Ant Design.

## Global Constraints

- Scope only covers detection and path persistence for ffmpeg, ffprobe, So-VITS-SVC Python + repo, RVC Python, UVR Python + model directory.
- Do not implement automatic installation, bundle scanning, CUDA/torch detection, model import, inference, or installers.
- Use existing `SettingsStore`; do not add a database.
- Use Python stdlib only for backend detection; do not add dependencies.
- Settings keys are exactly: `ffmpeg_path`, `ffprobe_path`, `svc_python`, `sovits_repo`, `rvc_python`, `uvr_python`, `uvr_model_dir`.
- Bridge methods are exactly: `get_runtime_status()`, `set_runtime_path(key, path)`, `check_runtime_component(key)`.
- Frontend keeps Runtime page state local; no global store.
- No file picker in this slice; use text inputs.

---

## File Structure

- Create `app/application/__init__.py` — package marker.
- Create `app/application/runtime_service.py` — runtime path persistence and component detection.
- Modify `app/api/bridge.py` — inject `RuntimeService` and expose runtime methods.
- Modify `web/src/api/types.ts` — runtime status types and DesktopApi methods.
- Modify `web/src/api/index.ts` — frontend wrapper and mock runtime API.
- Modify `web/src/pages/Runtime.tsx` — status table, path inputs, save/check buttons.

---

### Task 1: Backend RuntimeService and bridge API

**Files:**
- Create: `app/application/__init__.py`
- Create: `app/application/runtime_service.py`
- Modify: `app/api/bridge.py`

**Interfaces:**
- Consumes: `SettingsStore.get(key: str, default: Any = None) -> Any`, `SettingsStore.set(key: str, value: Any) -> None`.
- Produces: `RuntimeService.status() -> dict[str, Any]`
- Produces: `RuntimeService.set_path(key: str, path: str) -> dict[str, Any]`
- Produces: `RuntimeService.check_component(key: str) -> dict[str, Any]`
- Produces bridge methods: `get_runtime_status()`, `set_runtime_path(key, path)`, `check_runtime_component(key)`.

- [ ] **Step 1: Create backend service file**

Write `app/application/runtime_service.py`:

```python
"""Runtime path persistence and lightweight component checks."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import config
from infrastructure.storage import SettingsStore

RUNTIME_PATH_KEYS = {
    "ffmpeg_path",
    "ffprobe_path",
    "svc_python",
    "sovits_repo",
    "rvc_python",
    "uvr_python",
    "uvr_model_dir",
}

_COMPONENTS = {
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffprobe",
    "svc": "So-VITS-SVC",
    "rvc": "RVC",
    "uvr": "UVR",
}


class RuntimeService:
    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "components": [self.check_component(key) for key in _COMPONENTS],
            "paths": self._paths(),
        }

    def set_path(self, key: str, path: str) -> dict[str, Any]:
        key = str(key or "")
        if key not in RUNTIME_PATH_KEYS:
            return {"ok": False, "error": f"未知运行环境路径: {key}", **self.status()}
        self._settings.set(key, str(path or "").strip())
        return {"ok": True, **self.status()}

    def check_component(self, key: str) -> dict[str, Any]:
        key = str(key or "")
        if key == "ffmpeg":
            return self._check_command("ffmpeg", "ffmpeg_path", "ffmpeg")
        if key == "ffprobe":
            return self._check_command("ffprobe", "ffprobe_path", "ffprobe")
        if key == "svc":
            return self._component("svc", [
                self._file_check("svc_python", "SVC Python"),
                self._sovits_repo_check(),
            ])
        if key == "rvc":
            return self._component("rvc", [self._file_check("rvc_python", "RVC Python")])
        if key == "uvr":
            return self._component("uvr", [
                self._file_check("uvr_python", "UVR Python"),
                self._dir_check("uvr_model_dir", "UVR 模型目录"),
            ])
        return {
            "key": key,
            "name": key or "unknown",
            "status": "missing",
            "message": "未知组件",
            "checks": [],
        }

    def _paths(self) -> dict[str, str]:
        return {key: str(self._settings.get(key, "") or "") for key in sorted(RUNTIME_PATH_KEYS)}

    def _check_command(self, key: str, setting_key: str, exe: str) -> dict[str, Any]:
        configured = str(self._settings.get(setting_key, "") or "").strip()
        candidate = configured or shutil.which(exe) or ""
        exists = bool(candidate and (Path(candidate).exists() or shutil.which(candidate)))
        checks = [{
            "key": setting_key,
            "label": f"{exe} 路径",
            "ok": exists,
            "message": candidate if exists else f"未找到 {exe}",
        }]
        if exists:
            checks.append(self._version_check(candidate, exe))
        return self._component(key, checks)

    def _version_check(self, command: str, label: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [command, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                **config.subprocess_no_window(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"key": f"{label}_version", "label": f"{label} 版本", "ok": False, "message": str(exc)}
        first = (result.stdout or result.stderr or "").splitlines()[0] if (result.stdout or result.stderr) else ""
        return {
            "key": f"{label}_version",
            "label": f"{label} 版本",
            "ok": result.returncode == 0,
            "message": first or f"退出码 {result.returncode}",
        }

    def _file_check(self, setting_key: str, label: str) -> dict[str, Any]:
        value = str(self._settings.get(setting_key, "") or "").strip()
        ok = bool(value and Path(value).expanduser().is_file())
        return {"key": setting_key, "label": label, "ok": ok, "message": value if ok else f"未配置或文件不存在: {label}"}

    def _dir_check(self, setting_key: str, label: str) -> dict[str, Any]:
        value = str(self._settings.get(setting_key, "") or "").strip()
        ok = bool(value and Path(value).expanduser().is_dir())
        return {"key": setting_key, "label": label, "ok": ok, "message": value if ok else f"未配置或目录不存在: {label}"}

    def _sovits_repo_check(self) -> dict[str, Any]:
        value = str(self._settings.get("sovits_repo", "") or "").strip()
        target = Path(value).expanduser() / "inference" / "infer_tool.py" if value else Path()
        ok = bool(value and target.is_file())
        return {"key": "sovits_repo", "label": "So-VITS-SVC 仓库", "ok": ok, "message": value if ok else "未找到 inference/infer_tool.py"}

    def _component(self, key: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
        ok_count = sum(1 for check in checks if check.get("ok"))
        if checks and ok_count == len(checks):
            status = "ready"
            message = "已就绪"
        elif ok_count:
            status = "partial"
            message = "部分配置缺失"
        else:
            status = "missing"
            message = "未配置"
        return {"key": key, "name": _COMPONENTS.get(key, key), "status": status, "message": message, "checks": checks}
```

- [ ] **Step 2: Create package marker**

Create empty `app/application/__init__.py`.

- [ ] **Step 3: Modify bridge wiring**

Update `app/api/bridge.py` to import and inject the service:

```python
from application.runtime_service import RuntimeService
```

Change `Api.__init__` to accept runtime:

```python
class Api:
    def __init__(self, settings: SettingsStore, runtime: RuntimeService) -> None:
        self._settings = settings
        self._runtime = runtime
        self._window = None
```

Add methods inside `Api`:

```python
    def get_runtime_status(self) -> dict[str, Any]:
        return self._runtime.status()

    def set_runtime_path(self, key: str, path: str) -> dict[str, Any]:
        return self._runtime.set_path(key, path)

    def check_runtime_component(self, key: str) -> dict[str, Any]:
        return self._runtime.check_component(key)
```

Update `build_api()`:

```python
def build_api() -> Api:
    config.ensure_data_dirs()
    settings = SettingsStore(config.SETTINGS_DB)
    return Api(settings, RuntimeService(settings))
```

- [ ] **Step 4: Run backend smoke check**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
python3 -m py_compile app/api/bridge.py app/application/runtime_service.py
python3 - <<'PY'
import sys
sys.path.insert(0, 'app')
from api.bridge import build_api
api = build_api()
status = api.get_runtime_status()
assert 'components' in status, status
assert len(status['components']) == 5, status
assert api.set_runtime_path('ffmpeg_path', '')['ok'] is True
assert api.set_runtime_path('bad_key', 'x')['ok'] is False
print('runtime backend smoke ok')
PY
```

Expected output includes:

```text
runtime backend smoke ok
```

- [ ] **Step 5: Commit backend runtime service**

```bash
git add app/application app/api/bridge.py
git commit -m "feat: add runtime status backend

问题描述: 运行环境页缺少后端检测与路径保存 API。
修复思路: 增加 RuntimeService，复用 SettingsStore 保存手动路径，并通过 bridge 暴露状态、保存和单组件检测方法。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Frontend Runtime API types and wrapper

**Files:**
- Modify: `web/src/api/types.ts`
- Modify: `web/src/api/index.ts`

**Interfaces:**
- Consumes bridge methods from Task 1.
- Produces TypeScript types: `RuntimeStatus`, `RuntimeComponentStatus`, `RuntimeCheck`, `SetRuntimePathResult`.
- Produces wrapper methods: `api.getRuntimeStatus()`, `api.setRuntimePath(key, path)`, `api.checkRuntimeComponent(key)`.

- [ ] **Step 1: Extend frontend types**

Append to `web/src/api/types.ts`:

```ts
export type RuntimeComponentKey = 'ffmpeg' | 'ffprobe' | 'svc' | 'rvc' | 'uvr'
export type RuntimeStatusValue = 'ready' | 'missing' | 'partial' | 'error'

export interface RuntimeCheck {
  key: string
  label: string
  ok: boolean
  message: string
}

export interface RuntimeComponentStatus {
  key: RuntimeComponentKey
  name: string
  status: RuntimeStatusValue
  message: string
  checks: RuntimeCheck[]
}

export interface RuntimeStatus {
  components: RuntimeComponentStatus[]
  paths: Record<string, string>
}

export interface SetRuntimePathResult extends RuntimeStatus {
  ok: boolean
  error?: string
}
```

Extend `DesktopApi`:

```ts
  get_runtime_status: () => Promise<RuntimeStatus>
  set_runtime_path: (key: string, path: string) => Promise<SetRuntimePathResult>
  check_runtime_component: (key: string) => Promise<RuntimeComponentStatus>
```

- [ ] **Step 2: Extend mock and wrapper**

Update `web/src/api/index.ts` imports:

```ts
import type { AppStatus, RuntimeComponentStatus, RuntimeStatus, SetRuntimePathResult, SetSettingResult } from './types'
```

Add mock path state and components:

```ts
const mockRuntimePaths: Record<string, string> = {
  ffmpeg_path: '',
  ffprobe_path: '',
  rvc_python: '',
  sovits_repo: '',
  svc_python: '',
  uvr_model_dir: '',
  uvr_python: '',
}

function mockComponent(key: RuntimeComponentStatus['key'], name: string): RuntimeComponentStatus {
  return { key, name, status: 'missing', message: '浏览器 mock：未检测', checks: [] }
}

function mockRuntimeStatus(): RuntimeStatus {
  return {
    components: [
      mockComponent('ffmpeg', 'ffmpeg'),
      mockComponent('ffprobe', 'ffprobe'),
      mockComponent('svc', 'So-VITS-SVC'),
      mockComponent('rvc', 'RVC'),
      mockComponent('uvr', 'UVR'),
    ],
    paths: mockRuntimePaths,
  }
}
```

Add mock methods:

```ts
  async get_runtime_status(): Promise<RuntimeStatus> {
    return mockRuntimeStatus()
  },
  async set_runtime_path(key: string, value: string): Promise<SetRuntimePathResult> {
    mockRuntimePaths[key] = value
    return { ok: true, ...mockRuntimeStatus() }
  },
  async check_runtime_component(key: string): Promise<RuntimeComponentStatus> {
    return mockRuntimeStatus().components.find((it) => it.key === key) ?? mockComponent('ffmpeg', key)
  },
```

Add wrapper methods:

```ts
  getRuntimeStatus: async () => (await desktop()).get_runtime_status(),
  setRuntimePath: async (key: string, path: string) => (await desktop()).set_runtime_path(key, path),
  checkRuntimeComponent: async (key: string) => (await desktop()).check_runtime_component(key),
```

- [ ] **Step 3: Run frontend type/build check**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
npm run build --prefix web
```

Expected: build exits 0.

- [ ] **Step 4: Commit frontend API wrapper**

```bash
git add web/src/api/types.ts web/src/api/index.ts
git commit -m "feat: add runtime frontend API wrapper

问题描述: 前端缺少 Runtime Manager 的类型和 bridge 封装。
修复思路: 增加运行环境状态类型、桌面 API 方法和浏览器 mock fallback，供 Runtime 页面调用。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Runtime page UI

**Files:**
- Modify: `web/src/pages/Runtime.tsx`

**Interfaces:**
- Consumes: `api.getRuntimeStatus()`, `api.setRuntimePath(key, path)`, `RuntimeStatus`.
- Produces: `/runtime` page with component table, seven path inputs, save/check button, refresh button.

- [ ] **Step 1: Replace Runtime page with local-state UI**

Write `web/src/pages/Runtime.tsx`:

```tsx
import { Button, Card, Form, Input, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { RuntimeComponentStatus, RuntimeStatus, RuntimeStatusValue } from '../api/types'

const PATH_FIELDS = [
  ['ffmpeg_path', 'ffmpeg 路径'],
  ['ffprobe_path', 'ffprobe 路径'],
  ['svc_python', 'SVC Python'],
  ['sovits_repo', 'So-VITS-SVC 仓库'],
  ['rvc_python', 'RVC Python'],
  ['uvr_python', 'UVR Python'],
  ['uvr_model_dir', 'UVR 模型目录'],
] as const

const STATUS_COLOR: Record<RuntimeStatusValue, string> = {
  ready: 'green',
  partial: 'orange',
  missing: 'default',
  error: 'red',
}

export function Runtime() {
  const [form] = Form.useForm<Record<string, string>>()
  const [status, setStatus] = useState<RuntimeStatus | null>(null)
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      const next = await api.getRuntimeStatus()
      setStatus(next)
      form.setFieldsValue(next.paths)
    } finally {
      setLoading(false)
    }
  }

  async function save() {
    setLoading(true)
    try {
      let next: RuntimeStatus | null = null
      const values = form.getFieldsValue()
      for (const [key] of PATH_FIELDS) {
        const result = await api.setRuntimePath(key, values[key] ?? '')
        if (!result.ok) {
          message.error(result.error ?? '保存失败')
          return
        }
        next = result
      }
      setStatus(next)
      if (next) form.setFieldsValue(next.paths)
      message.success('已保存并检测')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        title="运行环境"
        extra={
          <Space>
            <Button onClick={refresh} loading={loading}>刷新状态</Button>
            <Button type="primary" onClick={save} loading={loading}>保存并检测</Button>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary">
          先手动填写已有运行环境路径；自动安装和整合包扫描后续再加。
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          {PATH_FIELDS.map(([key, label]) => (
            <Form.Item key={key} name={key} label={label}>
              <Input placeholder="留空则使用 PATH 或显示未配置" allowClear />
            </Form.Item>
          ))}
        </Form>
      </Card>

      <Card title="组件状态">
        <Table<RuntimeComponentStatus>
          rowKey="key"
          loading={loading}
          dataSource={status?.components ?? []}
          pagination={false}
          columns={[
            { title: '组件', dataIndex: 'name' },
            {
              title: '状态',
              dataIndex: 'status',
              render: (value: RuntimeStatusValue) => <Tag color={STATUS_COLOR[value]}>{value}</Tag>,
            },
            { title: '说明', dataIndex: 'message' },
            {
              title: '检查项',
              render: (_, row) => (
                <Space direction="vertical" size={2}>
                  {row.checks.map((check) => (
                    <Typography.Text key={check.key} type={check.ok ? 'success' : 'secondary'}>
                      {check.ok ? '✓' : '×'} {check.label}: {check.message}
                    </Typography.Text>
                  ))}
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  )
}
```

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
npm run build --prefix web
```

Expected: build exits 0.

- [ ] **Step 3: Commit Runtime page**

```bash
git add web/src/pages/Runtime.tsx
git commit -m "feat: add runtime manager page

问题描述: /runtime 页面只有占位文案，无法查看或保存运行环境路径。
修复思路: 使用 Ant Design 表单和表格展示五个组件状态，并支持保存七个手动路径后重新检测。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: End-to-end verification and README note

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: completed backend and frontend runtime manager.
- Produces: README note describing `/runtime` manual path mode.

- [ ] **Step 1: Add README Runtime note**

In `README.md`, under “已实现功能”, add:

```markdown
### 运行环境管理

- `/runtime` 页面可查看 ffmpeg / ffprobe / SVC / RVC / UVR 状态
- 支持手动填写并保存 runtime 路径
- 当前仅做轻量检测，不做自动安装、CUDA 检测或整合包扫描
```

- [ ] **Step 2: Run full verification**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
python3 -m py_compile app/config.py app/main.py app/api/bridge.py app/infrastructure/storage.py app/application/runtime_service.py
python3 - <<'PY'
import sys
sys.path.insert(0, 'app')
from api.bridge import build_api
api = build_api()
status = api.get_runtime_status()
assert 'components' in status, status
assert len(status['components']) == 5, status
assert api.set_runtime_path('ffmpeg_path', '')['ok'] is True
assert api.set_runtime_path('bad_key', 'x')['ok'] is False
print('runtime backend smoke ok')
PY
npm run build --prefix web
```

Expected output includes:

```text
runtime backend smoke ok
```

and npm build exits 0.

- [ ] **Step 3: Commit README + verification marker**

```bash
git add README.md
git commit -m "docs: document runtime manager slice

问题描述: README 未说明 Runtime Manager 当前支持的手动路径检测能力。
修复思路: 补充 /runtime 页面能力与当前限制，明确自动安装和深度检测仍属后续阶段。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

- Spec coverage: Tasks cover backend service, bridge methods, TypeScript types, frontend wrapper, Runtime page UI, README note, and verification commands.
- Deliberate deferrals are preserved: no file picker, no auto install, no torch/CUDA/import checks, no bundle scanning.
- Placeholder scan: no TBD/TODO/fill-in sections.
- Type consistency: backend status keys match frontend `RuntimeComponentKey`; bridge snake_case maps to frontend camelCase wrapper.

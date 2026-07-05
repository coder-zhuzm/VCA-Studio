# Desktop Shell And Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable VCA-Studio increment: React frontend, pywebview desktop shell, bridge API, and JSON settings storage.

**Architecture:** Keep the first slice thin: Python owns app config, pywebview startup, bridge methods, and JSON persistence; React owns routing, display, and API calls. Browser dev uses a mock fallback; desktop mode calls `window.pywebview.api`.

**Tech Stack:** Python 3.10+, pywebview, uv, React 19, TypeScript, Vite, React Router, Ant Design.

## Global Constraints

- Keep P0 scope to desktop shell + storage; do not implement runtime detection, model import, inference, or installers in this plan.
- Do not copy the Vue frontend from `xb-svcb`; this project uses React + Vite + TypeScript.
- Reuse the reference repo patterns only where they are small and proven: `config.py`, `storage.py`, `bridge.py`, `main.py` shape.
- Main app metadata: `APP_NAME = "VCA-Studio"`, `APP_TITLE = "VCA-Studio"`, `APP_VERSION = "0.1.0"`.
- User data directory name: `.vca_studio`.
- Environment variable override: `VCA_DATA_DIR`.
- No new database; use JSON files.
- No new desktop shell; use pywebview.
- Keep files focused and small; do not scaffold future modules.

---

## File Structure

- `app/pyproject.toml` — Python project metadata and runtime deps.
- `app/config.py` — app metadata, source/frozen paths, frontend dist path, data directory, subprocess helper.
- `app/infrastructure/storage.py` — thread-safe JSON store and settings store.
- `app/api/bridge.py` — pywebview-exposed API and composition root.
- `app/main.py` — desktop entrypoint loading Vite dev server or built frontend.
- `web/package.json` — frontend deps and scripts.
- `web/index.html` — Vite HTML entry.
- `web/tsconfig.json`, `web/tsconfig.app.json`, `web/vite.config.ts` — TypeScript/Vite config.
- `web/src/api/types.ts` — shared frontend API types.
- `web/src/api/index.ts` — pywebview bridge wrapper and browser mock fallback.
- `web/src/pages/*.tsx` — five P0 route pages.
- `web/src/App.tsx` — app layout and routes.
- `web/src/main.tsx` — React entry.
- `.gitignore` — replace generated Python template with VCA-Studio ignores from project report.

---

### Task 1: Python desktop shell skeleton

**Files:**
- Create: `app/pyproject.toml`
- Create: `app/config.py`
- Create: `app/api/__init__.py`
- Create: `app/api/bridge.py`
- Create: `app/infrastructure/__init__.py`
- Create: `app/infrastructure/storage.py`
- Create: `app/main.py`

**Interfaces:**
- Produces: `config.APP_NAME: str`, `config.APP_TITLE: str`, `config.APP_VERSION: str`, `config.DATA_DIR: Path`, `config.SETTINGS_DB: Path`, `config.DIST_INDEX: Path`, `config.subprocess_no_window() -> dict`
- Produces: `SettingsStore.get(key: str, default: Any = None) -> Any`, `SettingsStore.set(key: str, value: Any) -> None`, `SettingsStore.all() -> dict[str, Any]`
- Produces: `build_api() -> Api`
- Produces bridge methods: `get_app_status() -> dict[str, Any]`, `get_settings() -> dict[str, Any]`, `set_setting(key: str, value: Any) -> dict[str, Any]`

- [ ] **Step 1: Create Python project metadata**

Write `app/pyproject.toml`:

```toml
[project]
name = "vca-studio-app"
version = "0.1.0"
description = "VCA-Studio desktop backend"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "pywebview>=6.2.1",
]

[tool.uv]
package = false
```

- [ ] **Step 2: Create config module**

Write `app/config.py`:

```python
"""App metadata, paths, and runtime helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "VCA-Studio"
APP_TITLE = "VCA-Studio"
APP_VERSION = "0.1.0"
DATA_DIR_NAME = ".vca_studio"

_FROZEN = bool(getattr(sys, "frozen", False))
if _FROZEN:
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = Path(__file__).resolve().parent

ROOT_DIR = BASE_DIR
DIST_INDEX = BUNDLE_DIR / "web" / "dist" / "index.html" if _FROZEN else ROOT_DIR / "web" / "dist" / "index.html"


def _default_data_dir() -> Path:
    env = os.environ.get("VCA_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME / DATA_DIR_NAME
    return ROOT_DIR / DATA_DIR_NAME


DATA_DIR = _default_data_dir()
SETTINGS_DB = DATA_DIR / "settings.json"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def subprocess_no_window() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        "startupinfo": startupinfo,
    }
```

- [ ] **Step 3: Create JSON settings storage**

Write `app/infrastructure/storage.py`:

```python
"""Small thread-safe JSON storage."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: Path, default: Any) -> None:
        self._path = path
        self._default = default
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write(default)

    def read(self) -> Any:
        with self._lock:
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return self._default

    def write(self, data: Any) -> None:
        with self._lock:
            self._write(data)

    def _write(self, data: Any) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path, {})

    def all(self) -> dict[str, Any]:
        data = self._store.read()
        return data if isinstance(data, dict) else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.all().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self.all()
        data[key] = value
        self._store.write(data)
```

- [ ] **Step 4: Create bridge API**

Write `app/api/bridge.py`:

```python
"""pywebview JavaScript API bridge."""

from __future__ import annotations

from typing import Any

import config
from infrastructure.storage import SettingsStore


class Api:
    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings
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


def build_api() -> Api:
    config.ensure_data_dirs()
    return Api(SettingsStore(config.SETTINGS_DB))
```

- [ ] **Step 5: Create package markers**

Write empty files:

```text
app/api/__init__.py
app/infrastructure/__init__.py
```

- [ ] **Step 6: Create desktop entrypoint**

Write `app/main.py`:

```python
"""VCA-Studio desktop entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import webview

import config
from api.bridge import build_api

DEV_URL = "http://localhost:5173"


def _url(dev: bool) -> str:
    if dev:
        return DEV_URL
    index = Path(config.DIST_INDEX)
    if not index.exists():
        raise FileNotFoundError(f"Frontend build not found: {index}")
    return index.as_uri()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Load Vite dev server")
    args = parser.parse_args()

    api = build_api()
    window = webview.create_window(
        config.APP_TITLE,
        _url(args.dev),
        js_api=api,
        width=1200,
        height=780,
        min_size=(960, 640),
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Verify Python syntax**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio/app
python3 -m py_compile config.py main.py api/bridge.py infrastructure/storage.py
```

Expected: command exits with code 0 and no output.

- [ ] **Step 8: Commit Python shell**

```bash
git add app
git commit -m "feat: add desktop shell backend

问题描述: VCA-Studio 缺少可运行的 Python 桌面壳和本地设置存储。
修复思路: 增加 pywebview 入口、bridge API 与 JSON SettingsStore，先打通最小桌面闭环.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: React frontend skeleton

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.app.json`
- Create: `web/vite.config.ts`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/api/types.ts`
- Create: `web/src/api/index.ts`
- Create: `web/src/pages/Home.tsx`
- Create: `web/src/pages/Runtime.tsx`
- Create: `web/src/pages/Models.tsx`
- Create: `web/src/pages/Create.tsx`
- Create: `web/src/pages/Works.tsx`

**Interfaces:**
- Consumes: bridge methods from Task 1.
- Produces: `api.getAppStatus() -> Promise<AppStatus>`, `api.getSettings() -> Promise<Record<string, unknown>>`, `api.setSetting(key: string, value: unknown) -> Promise<SetSettingResult>`.

- [ ] **Step 1: Create frontend package metadata**

Write `web/package.json`:

```json
{
  "name": "vca-studio-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "antd": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "react-router-dom": "latest"
  },
  "devDependencies": {
    "@types/react": "latest",
    "@types/react-dom": "latest"
  },
  "engines": {
    "node": ">=20.19.0"
  }
}
```

- [ ] **Step 2: Create Vite config and TypeScript config**

Write `web/vite.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
```

Write `web/tsconfig.json`:

```json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }]
}
```

Write `web/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create HTML entry**

Write `web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>VCA-Studio</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Create API types and bridge wrapper**

Write `web/src/api/types.ts`:

```ts
export interface AppStatus {
  name: string
  title: string
  version: string
  data_dir: string
  dist_index: string
}

export interface SetSettingResult {
  ok: boolean
  settings: Record<string, unknown>
}

export interface DesktopApi {
  get_app_status: () => Promise<AppStatus>
  get_settings: () => Promise<Record<string, unknown>>
  set_setting: (key: string, value: unknown) => Promise<SetSettingResult>
}

declare global {
  interface Window {
    pywebview?: {
      api: DesktopApi
    }
  }
}
```

Write `web/src/api/index.ts`:

```ts
import type { AppStatus, SetSettingResult } from './types'

const mockSettings: Record<string, unknown> = {}

const mock = {
  async get_app_status(): Promise<AppStatus> {
    return {
      name: 'VCA-Studio',
      title: 'VCA-Studio',
      version: '0.1.0',
      data_dir: '.vca_studio',
      dist_index: 'web/dist/index.html',
    }
  },
  async get_settings(): Promise<Record<string, unknown>> {
    return mockSettings
  },
  async set_setting(key: string, value: unknown): Promise<SetSettingResult> {
    mockSettings[key] = value
    return { ok: true, settings: mockSettings }
  },
}

function desktop() {
  return window.pywebview?.api ?? mock
}

export const api = {
  getAppStatus: () => desktop().get_app_status(),
  getSettings: () => desktop().get_settings(),
  setSetting: (key: string, value: unknown) => desktop().set_setting(key, value),
}
```

- [ ] **Step 5: Create pages**

Write `web/src/pages/Home.tsx`:

```tsx
import { Card, Descriptions, Spin } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AppStatus } from '../api/types'

export function Home() {
  const [status, setStatus] = useState<AppStatus | null>(null)

  useEffect(() => {
    api.getAppStatus().then(setStatus)
  }, [])

  if (!status) return <Spin />

  return (
    <Card title="首页">
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="应用">{status.title}</Descriptions.Item>
        <Descriptions.Item label="版本">{status.version}</Descriptions.Item>
        <Descriptions.Item label="数据目录">{status.data_dir}</Descriptions.Item>
      </Descriptions>
    </Card>
  )
}
```

Write `web/src/pages/Runtime.tsx`:

```tsx
import { Card, Typography } from 'antd'

export function Runtime() {
  return (
    <Card title="运行环境">
      <Typography.Text type="secondary">下一步接入 ffmpeg / SVC / RVC / UVR 检测。</Typography.Text>
    </Card>
  )
}
```

Write `web/src/pages/Models.tsx`:

```tsx
import { Card, Typography } from 'antd'

export function Models() {
  return (
    <Card title="模型管理">
      <Typography.Text type="secondary">下一步接入本地 SVC / RVC 模型导入。</Typography.Text>
    </Card>
  )
}
```

Write `web/src/pages/Create.tsx`:

```tsx
import { Card, Typography } from 'antd'

export function Create() {
  return (
    <Card title="新建翻唱">
      <Typography.Text type="secondary">下一步接入 song / vocals / stems 输入模式。</Typography.Text>
    </Card>
  )
}
```

Write `web/src/pages/Works.tsx`:

```tsx
import { Card, Typography } from 'antd'

export function Works() {
  return (
    <Card title="作品库">
      <Typography.Text type="secondary">下一步接入任务列表、日志和导出。</Typography.Text>
    </Card>
  )
}
```

- [ ] **Step 6: Create app layout and routes**

Write `web/src/App.tsx`:

```tsx
import { Layout, Menu, Typography } from 'antd'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Create } from './pages/Create'
import { Home } from './pages/Home'
import { Models } from './pages/Models'
import { Runtime } from './pages/Runtime'
import { Works } from './pages/Works'

const items = [
  { key: '/', label: <Link to="/">首页</Link> },
  { key: '/runtime', label: <Link to="/runtime">运行环境</Link> },
  { key: '/models', label: <Link to="/models">模型管理</Link> },
  { key: '/create', label: <Link to="/create">新建翻唱</Link> },
  { key: '/works', label: <Link to="/works">作品库</Link> },
]

export function App() {
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider width={220} theme="dark">
        <Typography.Title level={4} style={{ color: 'white', padding: '20px 20px 8px', margin: 0 }}>
          VCA-Studio
        </Typography.Title>
        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={items} />
      </Layout.Sider>
      <Layout>
        <Layout.Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/runtime" element={<Runtime />} />
            <Route path="/models" element={<Models />} />
            <Route path="/create" element={<Create />} />
            <Route path="/works" element={<Works />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
```

Write `web/src/main.tsx`:

```tsx
import 'antd/dist/reset.css'

import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 7: Install and build frontend**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio/web
npm install
npm run build
```

Expected: `web/dist/index.html` exists and build exits with code 0.

- [ ] **Step 8: Commit frontend skeleton**

```bash
git add web
git commit -m "feat: add React desktop frontend shell

问题描述: VCA-Studio 缺少 P0 页面和浏览器开发入口。
修复思路: 使用 React + Vite + TypeScript 建立五个 P0 路由，并通过 API mock/pywebview bridge 读取应用状态.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Project ignores and end-to-end smoke check

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1 backend, Task 2 frontend.
- Produces: repository ignores generated runtimes, data, node modules, frontend build output, model weights, and audio files.

- [ ] **Step 1: Replace `.gitignore` with VCA-Studio-focused ignores**

Write `.gitignore`:

```gitignore
# ===== Python =====
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
build/
dist/
wheels/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# ===== Virtual envs =====
.venv/
.venv-*/
env/
venv/
app/.venv/

# ===== Frontend / Node =====
node_modules/
web/dist/
web/dist-ssr/
coverage/
*.local
.eslintcache
*.tsbuildinfo
*.timestamp-*-*.mjs

# ===== Runtime / generated AI env =====
runtime/
engines/
models/
.venv-svc/
.venv-rvc/
.venv-uvr/
.venv-hub/

# ===== User data =====
.vca_studio/
data_home.json

# ===== Large model / audio files =====
*.pth
*.onnx
*.pt
*.ckpt
*.safetensors
*.bin
*.index
*.npy
*.npz
*.mp3
*.wav
*.flac
*.m4a
*.ogg
*.aac

# ===== Logs =====
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# ===== IDE / Editor =====
.idea/
.vscode/*
!.vscode/extensions.json
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?

# ===== OS =====
.DS_Store
Thumbs.db
desktop.ini

# ===== Local scratch =====
.tmp/
```

- [ ] **Step 2: Verify Python bridge directly**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio/app
python3 - <<'PY'
from api.bridge import build_api
api = build_api()
print(api.get_app_status()["name"])
print(api.set_setting("smoke", "ok")["settings"]["smoke"])
PY
```

Expected output:

```text
VCA-Studio
ok
```

- [ ] **Step 3: Verify production frontend build path exists after build**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio/web
npm run build
python3 - <<'PY'
from pathlib import Path
p = Path('dist/index.html')
assert p.exists(), p
print(p)
PY
```

Expected output contains:

```text
dist/index.html
```

- [ ] **Step 4: Verify repository status contains only intended tracked sources**

Run:

```bash
cd /Users/zhuzm/Documents/zhuzm/code/github/VCA-Studio
git status --short
```

Expected: source files are staged or unstaged as intended; `web/node_modules`, `web/dist`, and `.vca_studio` are not listed.

- [ ] **Step 5: Commit ignores and smoke verification**

```bash
git add .gitignore
git commit -m "chore: align ignores for VCA-Studio runtime files

问题描述: 默认 Python .gitignore 未覆盖 VCA-Studio 的 runtime、模型、音频和前端产物。
修复思路: 按 P0 分发策略忽略生成环境、用户数据、大模型和音频文件，保持主仓库轻量.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

- Spec coverage: first runnable increment covers desktop shell, pywebview bridge, browser mock fallback, JSON settings storage, five P0 routes, and production build loading.
- Scope check: runtime detection, model import, inference, works queue, export, and installers are intentionally excluded; they are separate follow-up plans.
- Placeholder scan: no `TBD`, no `TODO`, no undefined future method references.
- Type consistency: Python bridge exposes snake_case methods; frontend wrapper maps them to camelCase helpers.

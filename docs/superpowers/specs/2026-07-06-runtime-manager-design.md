# Runtime Manager Design

## Goal

Add the first Runtime Manager slice: users can view runtime component status, manually save paths, and re-check components from the `/runtime` page.

## Scope

This spec covers only detection and path persistence for:

- ffmpeg
- ffprobe
- So-VITS-SVC Python + repo
- RVC Python
- UVR Python + model directory

This spec does not cover automatic installation, bundle scanning, CUDA/torch detection, model import, inference, or installers.

## Backend design

Create `app/application/runtime_service.py`.

The service uses the existing `SettingsStore` and Python stdlib only.

### Settings keys

```text
ffmpeg_path
ffprobe_path
svc_python
sovits_repo
rvc_python
uvr_python
uvr_model_dir
```

### Bridge API

Add these methods to `Api` in `app/api/bridge.py`:

```text
get_runtime_status()
set_runtime_path(key, path)
check_runtime_component(key)
```

`build_api()` constructs `RuntimeService(settings)` and injects it into `Api`.

### Status shape

Return a payload shaped like:

```ts
interface RuntimeStatus {
  components: RuntimeComponentStatus[]
  paths: Record<string, string>
}

interface RuntimeComponentStatus {
  key: 'ffmpeg' | 'ffprobe' | 'svc' | 'rvc' | 'uvr'
  name: string
  status: 'ready' | 'missing' | 'partial' | 'error'
  message: string
  checks: RuntimeCheck[]
}

interface RuntimeCheck {
  key: string
  label: string
  ok: boolean
  message: string
}
```

### Detection rules

| Component | Ready when |
|---|---|
| ffmpeg | configured path or PATH candidate exists and `ffmpeg -version` exits 0 |
| ffprobe | configured path or PATH candidate exists and `ffprobe -version` exits 0 |
| svc | `svc_python` file exists and `sovits_repo/inference/infer_tool.py` exists |
| rvc | `rvc_python` file exists |
| uvr | `uvr_python` file exists and `uvr_model_dir` is a directory |

If some checks pass and some fail, status is `partial`. If no required checks pass, status is `missing`. If a subprocess raises or times out, status is `error` for that check/component.

`set_runtime_path(key, path)` accepts only the settings keys listed above. It trims whitespace, saves the value, and returns the full runtime status.

## Frontend design

Update:

- `web/src/api/types.ts`
- `web/src/api/index.ts`
- `web/src/pages/Runtime.tsx`

The Runtime page shows:

- status table for the five components
- path inputs for all seven settings keys
- `保存并检测` button
- `刷新状态` button

Use existing Ant Design components. Keep state local to the page; no global store yet.

## Error handling

- Backend never throws for missing tools; it returns status payloads.
- Invalid setting key returns `{ ok: false, error: '...' }` from bridge.
- Frontend displays component messages and a small error message if save fails.

## Testing / verification

Minimum checks:

```bash
python3 -m py_compile app/api/bridge.py app/application/runtime_service.py
npm run build --prefix web
```

Backend smoke:

```python
from api.bridge import build_api
api = build_api()
status = api.get_runtime_status()
assert 'components' in status
assert api.set_runtime_path('ffmpeg_path', '')['ok'] is True
assert api.set_runtime_path('bad_key', 'x')['ok'] is False
```

Frontend build must pass.

## Deliberate deferrals

- No file picker. Text inputs are enough for the first slice.
- No auto install. Runtime setup is a later feature.
- No torch/CUDA/import checks. Add once path saving is stable.
- No bundle scanning. Add after manual path mode works on Windows.

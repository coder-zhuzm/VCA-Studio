# ModelService Design

## Goal

Add local model management for the P0 cover workflow. Users can import, list, check, delete, and set default models from the `/models` page.

## Scope

This spec supports both:

- RVC model import
- So-VITS-SVC model import

This spec does not cover inference, ModelScope, zip extraction, drag/drop, automatic format discovery, or file picker dialogs.

## Supported formats

### RVC

Required:

```text
checkpoint .pth
```

Optional:

```text
.index
```

### So-VITS-SVC

Required:

```text
checkpoint .pth
config.json
```

Optional:

```text
diffusion .pt
diffusion_config .yaml / .yml
```

## Storage

Use existing JSON storage style.

New paths:

```text
DATA_DIR/models.json
DATA_DIR/models/<model_id>/
```

Model import copies user-provided files into:

```text
DATA_DIR/models/<model_id>/
```

The app should not keep depending on external source paths after import.

## Backend design

Create `app/application/model_service.py`.

Add `MODELS_DIR` and `MODELS_DB` to `app/config.py`.

Use a small list repository or equivalent JSON list storage. If `ListRepository` does not exist yet, add the minimal version to `app/infrastructure/storage.py`.

### Model record

```ts
interface ModelRecord {
  id: string
  name: string
  framework: 'rvc' | 'so-vits-svc'
  files: Record<string, string>
  status: 'ready' | 'missing' | 'error'
  is_default: boolean
  created_at: string
  updated_at: string
  checks: ModelCheck[]
}

interface ModelCheck {
  key: string
  label: string
  ok: boolean
  message: string
}
```

`files` values are stored as strings pointing to copied files under `DATA_DIR/models/<model_id>/`.

### Import payload

```ts
interface ImportModelPayload {
  name: string
  framework: 'rvc' | 'so-vits-svc'
  checkpoint_path: string
  index_path?: string
  config_path?: string
  diffusion_path?: string
  diffusion_config_path?: string
}
```

### Bridge API

Add these methods to `Api`:

```text
list_models()
import_model(payload)
delete_model(id)
check_model(id)
set_default_model(id)
```

### Behavior

`import_model(payload)`:

1. Validate framework.
2. Validate required files by framework.
3. Create `model_<uuid>` directory under `MODELS_DIR`.
4. Copy provided files into that directory using simple role-based names:
   - `checkpoint` keeps source suffix, normally `.pth`
   - `index` keeps `.index`
   - `config` becomes `config.json`
   - `diffusion` keeps `.pt`
   - `diffusion_config` keeps `.yaml` or `.yml`
5. Create model record.
6. Run `check_model(id)` and persist updated status/checks.
7. If this is the first model, set `is_default = true`.
8. Return `{ ok: true, model }`.

`list_models()` returns newest-first model records.

`delete_model(id)`:

1. Remove record.
2. Delete only the model directory if it is inside `MODELS_DIR`.
3. If deleted model was default, make the newest remaining model default.
4. Return `{ ok: true, models }`.

`check_model(id)`:

- Re-check copied file existence.
- Persist `status` and `checks`.
- Return `{ ok: true, model }`.

`set_default_model(id)`:

- Set only the target model as default.
- Return `{ ok: true, models }`.

Invalid input returns `{ ok: false, error: '...' }`; do not throw for user mistakes.

## Frontend design

Update:

- `web/src/api/types.ts`
- `web/src/api/index.ts`
- `web/src/pages/Models.tsx`

The `/models` page shows:

- Import form
- Framework selector: `rvc` / `so-vits-svc`
- Text path inputs
- Model table
- Actions: check, set default, delete

Field visibility:

| Framework | Fields |
|---|---|
| rvc | name, checkpoint_path, index_path |
| so-vits-svc | name, checkpoint_path, config_path, diffusion_path, diffusion_config_path |

Use local component state only. No global store yet.

## Error handling

- Backend validates required files before copying.
- Backend returns readable errors for invalid framework, missing required files, and unknown model id.
- Frontend displays errors with `message.error`.
- Delete action uses browser confirm or Ant Design Popconfirm.

## Testing / verification

Minimum checks:

```bash
python3 -m py_compile app/config.py app/api/bridge.py app/application/model_service.py app/infrastructure/storage.py
npm run build --prefix web
```

Backend smoke should create temporary fake model files and verify:

```python
from api.bridge import build_api
api = build_api()
assert isinstance(api.list_models(), list)
assert api.import_model({'framework': 'bad'})['ok'] is False
# RVC import with fake .pth succeeds
# So-VITS-SVC import with fake .pth + config.json succeeds
# set_default_model works
# delete_model removes the record
```

## Deliberate deferrals

- No file picker. Text paths are enough for first slice.
- No model zip import.
- No ModelScope.
- No inference.
- No deep model validation or torch import.
- No tag/rating/favorite metadata.

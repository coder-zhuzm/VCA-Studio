# StemPreparer Design

**Date:** 2026-07-07

## Goal

Add the first `StemPreparer` backend slice. It standardizes user-provided audio inputs into a work directory so later services can run inference and mixing against predictable file roles.

This slice only performs lightweight validation and file copying. It does not separate vocals, decode audio, inspect codecs, call UVR, run inference, or create a task queue.

## Scope

Supported input modes:

- `song`: user provides one full-song file.
- `vocals`: user provides one existing vocal file.
- `stems`: user provides existing vocal and instrumental files.

The service validates required paths, copies source files into a generated work directory, and returns normalized role-to-path metadata.

## Non-Goals

- No UVR vocal separation.
- No automatic runtime installation.
- No audio decoding or duration/probe checks.
- No extension whitelist.
- No WorkService queue, retry, logs, or persisted work records.
- No Create page UI in this slice.

## Backend Design

Create `app/application/stem_preparer.py` with a small `StemPreparer` class.

```python
class StemPreparer:
    def __init__(self, works_dir: Path) -> None: ...
    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

`prepare()` accepts a pywebview-friendly dictionary:

```json
{
  "mode": "song | vocals | stems",
  "song_path": "...",
  "vocals_path": "...",
  "instrumental_path": "..."
}
```

Success response:

```json
{
  "ok": true,
  "work_id": "work_xxx",
  "mode": "stems",
  "files": {
    "vocals": "...",
    "instrumental": "..."
  }
}
```

Failure response:

```json
{
  "ok": false,
  "error": "..."
}
```

## File Layout

Use the existing application data directory and add a `works` subtree:

```text
<VCA_DATA_DIR>/works/<work_id>/input/
```

Role names become stable target filenames:

```text
song         -> input_song.<ext>
vocals       -> vocals.<ext>
instrumental -> instrumental.<ext>
```

The source extension is preserved and lowercased. User-provided filenames are not reused because downstream services should depend on stable roles rather than arbitrary source names.

Example for `stems` mode:

```text
works/work_ab12cd/input/vocals.wav
works/work_ab12cd/input/instrumental.wav
```

## Mode Rules

### `song`

Required field: `song_path`.

Output files:

```json
{"input_song": ".../input/input_song.wav"}
```

The output role is `input_song`, not `vocals`, because this slice does not separate the full song.

### `vocals`

Required field: `vocals_path`.

Output files:

```json
{"vocals": ".../input/vocals.wav"}
```

### `stems`

Required fields: `vocals_path`, `instrumental_path`.

Output files:

```json
{
  "vocals": ".../input/vocals.wav",
  "instrumental": ".../input/instrumental.wav"
}
```

## Validation and Errors

Validation is intentionally shallow:

- Unknown mode returns `ok: false` with `不支持的输入模式。`
- Missing required path returns `ok: false` with `缺少必填文件: <field>`.
- Non-file path returns `ok: false` with `文件不存在: <path>`.
- Copy errors return `ok: false` with the `OSError` message.

If any validation or copy fails, remove the newly created work directory to avoid partial prepared inputs.

## Bridge API

Modify `app/api/bridge.py` to instantiate `StemPreparer` and expose:

```python
def prepare_stems(self, payload: dict[str, Any]) -> dict[str, Any]:
    return self._stem_preparer.prepare(payload or {})
```

`build_api()` passes `config.WORKS_DIR` to `StemPreparer`.

## Config

Extend `app/config.py` with:

```python
WORKS_DIR = DATA_DIR / "works"
```

Update `ensure_data_dirs()` to create `WORKS_DIR`.

## Frontend

This slice is backend-only. Do not modify `/create` yet. The UI will consume `prepare_stems()` when WorkService and the Create flow are designed.

Optional TypeScript wrappers are also deferred to keep this slice small and avoid frontend build dependency issues unrelated to this backend contract.

## Verification

Run backend checks:

```bash
python3 -m py_compile app/config.py app/main.py app/api/bridge.py app/infrastructure/storage.py app/application/stem_preparer.py
```

Run smoke verification with temporary files:

- `song` mode copies one file and returns `files.input_song`.
- `vocals` mode copies one file and returns `files.vocals`.
- `stems` mode copies two files and returns `files.vocals` and `files.instrumental`.
- Invalid mode returns `ok: false`.
- Missing file returns `ok: false`.

No npm build is required unless a later implementation task changes frontend files.

## Implementation Notes

- Use Python stdlib only: `pathlib`, `shutil`, `uuid`.
- Generate IDs as `work_<12 hex chars>`.
- Keep the service independent from `ModelService` and `RuntimeService`.
- Do not persist work metadata yet; prepared files on disk are enough for this slice.

## Self-Review

- Placeholder scan: no TBD/TODO placeholders.
- Consistency: file roles, bridge method, and non-goals align with the selected lightweight-file-preparation approach.
- Scope: backend-only slice is small enough for one implementation plan.
- Ambiguity: `song` explicitly outputs `input_song` and does not imply separation.

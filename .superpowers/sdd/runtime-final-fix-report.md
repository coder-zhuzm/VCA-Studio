
## Final Runtime Manager fix

STATUS: fixed
- ffmpeg/ffprobe version subprocess exceptions now mark the check as `status: error`, and component aggregation returns `error` when any check is error.
- Manual ffmpeg/ffprobe paths expand `~` before existence checks and subprocess execution.

Tests:
- `python3 -m py_compile app/application/runtime_service.py app/api/bridge.py`
- Runtime bridge smoke: `~` path expansion, error aggregation, status/set-path bridge checks
- `npm run build --prefix web`

Concerns:
- Frontend build still reports the existing >500 kB chunk-size warning.

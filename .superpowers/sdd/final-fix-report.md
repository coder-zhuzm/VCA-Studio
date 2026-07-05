
## Final code-review fixes

- Set Vite `base: './'` so production desktop `file://` loads built assets relatively.
- Switched React Router from `BrowserRouter` to `HashRouter` for `file://` navigation.
- Made `SettingsStore.set()` lock the read-modify-write sequence.
- Added a short `file://` wait for delayed `window.pywebview.api` injection before using the browser mock.
- Pinned frontend dependencies to package-lock resolved exact versions and refreshed lockfile.

Checks:
- `npm install --prefix web`
- `python -m py_compile app/infrastructure/storage.py`
- `npm run build --prefix web`
- Smoke: built `web/dist/index.html` has `./assets/` and no root `/assets/` references.
- Storage smoke: concurrent `SettingsStore.set()` calls preserve all keys.

Concerns:
- Vite still warns that the main chunk is >500 kB; existing P0 shell scope, not fixed here.

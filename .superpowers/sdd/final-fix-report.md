
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

## Final review fix: pywebview dev-mode wait

- 问题描述：`web/src/api/index.ts` 只在 `file://` 下等待 `window.pywebview.api` 注入，桌面 dev 模式加载 `http://localhost:5173` 时可能过早回退 mock。
- 修复思路：移除 protocol 限制，统一短等 20 次、每次 25ms；无可靠 dev-mode 信号，保留浏览器 dev 的 mock fallback，并用 `ponytail` 注释标明 500ms ceiling。
- 验证：`npm run build --prefix web` 通过；复读 `desktop()` 确认 `http` 与 `file` 都会先等待注入再回退 mock。

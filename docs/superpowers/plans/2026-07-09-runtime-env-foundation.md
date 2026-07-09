# Runtime 环境基础（Win 优先）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 优先前提下，把 `/runtime` 打成可用的环境基础：用户自助完成 **ffmpeg + RVC（CUDA）** 检测/可选安装，组件 ready 后 `start_work` 不再因 runtime 未就绪失败。

**Architecture:** `HostProbe` 提供本机摘要；`RuntimeService` 仍是检测真相源；`RuntimeInstaller` 负责任务清单与用户确认后的安装/绑定，成功后写 `SettingsStore` 再重检。前端 `Runtime.tsx` 按「本机摘要 → 就绪清单 → 安装进度 → 全组件表 → 高级路径」重组，安装进行中全局禁用冲突操作。不改 `WorkService` 推理/混音流水线。

**Tech Stack:** Python 3.10+ stdlib, SettingsStore JSON, pywebview bridge, React + TypeScript + Ant Design, existing `runtime_service` / `runtime_installer` / `host_probe`.

**Spec:** `docs/superpowers/specs/2026-07-09-runtime-env-foundation-design.md`

## Global Constraints

- **范围 A + Windows 优先**（目标机：i5-12400 + RTX 2060 SUPER）；Mac 任务可保留但不作为本计划主验收。
- **软件安装器 ≠ 运行环境管理**；本计划不做 Inno/主程序安装包。
- **不做：** 强制首次向导、全局拦 Create、UVR/SVC 一键安装、整合包扫描、底模下载、环境端到端试跑按钮。
- **检测真相源：** 仅 `RuntimeService.status()` / `check_component()`；安装成功必须写路径后再检测。
- **安装：** 仅用户点击后执行；同时只允许一个 job；进行中禁用安装/保存路径/重测。
- **Settings keys（路径）：** `ffmpeg_path`, `ffprobe_path`, `svc_python`, `sovits_repo`, `rvc_python`, `uvr_python`, `uvr_model_dir`。
- **验收：** `ffmpeg` + `rvc` 为 `ready` 即可；不要求内置冒烟推理。
- 测试风格与仓库一致：可在 `app/` 下增加 `test_runtime_*.py` 用 `python test_runtime_*.py` 或 `python -m py_compile` + 小脚本断言；前端 `npm run build`。
- 中文 UI 文案；commit message 含问题/修复思路（用户规范）。

---

## File Structure

| 文件 | 职责 |
|------|------|
| `app/application/host_probe.py` | 本机 OS/GPU/推荐 device（已有，小补即可） |
| `app/application/runtime_service.py` | 组件检测真相源（已有） |
| `app/application/runtime_installer.py` | 任务清单、安装/绑定、进度日志（收敛 available 规则） |
| `app/api/bridge.py` | 暴露 host/runtime/install API（已有） |
| `app/test_runtime_installer.py` | **新建**：解析 ffmpeg、list_tasks available、并发拒绝 |
| `web/src/pages/Runtime.tsx` | 信息架构重组：就绪清单 + 进度 + 高级折叠 |
| `web/src/api/types.ts` / `index.ts` | 类型与 mock（若清单字段有扩展则同步） |
| `README.md` | Runtime 节与 Win 验收步骤与 spec 对齐 |

---

### Task 1: Installer 规则收敛 + 单元测试

**Files:**
- Modify: `app/application/runtime_installer.py`
- Create: `app/test_runtime_installer.py`
- Modify: `app/api/bridge.py`（仅当 `RuntimeInstaller` 构造/返回形状变化时）

**Interfaces:**
- Consumes: `SettingsStore`, `RuntimeService.status()`, `probe_host()`
- Produces:
  - `list_tasks() -> { ok, profile, tasks: [{ id, label, description, risk, available }] }`
  - `detect_ffmpeg() -> { ok, message?, error?, components?, paths?, ... }`
  - `run_task(task_id) -> dict`（`ffmpeg_path_hint` 同步；长任务后台 job）
  - Task ids: `ffmpeg_winget`, `ffmpeg_path_hint`, `rvc_venv_cuda`, `rvc_venv_cpu`（Mac 任务可保留）

- [ ] **Step 1: 写失败用例（ffmpeg 解析与 available）**

Create `app/test_runtime_installer.py`:

```python
"""RuntimeInstaller unit checks (no network, no real winget)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from application.runtime_installer import RuntimeInstaller
from application.runtime_service import RuntimeService
from infrastructure.storage import SettingsStore


def _installer(tmp: Path) -> RuntimeInstaller:
    settings = SettingsStore(tmp / "settings.json")
    runtime = RuntimeService(settings)
    return RuntimeInstaller(settings, runtime)


def test_resolve_prefers_configured_path() -> None:
    with tempfile.TemporaryDirectory() as root:
        tmp = Path(root)
        fake = tmp / "ffmpeg"
        fake.write_text("x")
        inst = _installer(tmp)
        inst._settings.set("ffmpeg_path", str(fake))
        resolved = inst._resolve_ffmpeg_paths()
        assert resolved is not None
        assert resolved[0] == str(fake)


def test_list_tasks_disables_winget_when_ffmpeg_ready() -> None:
    with tempfile.TemporaryDirectory() as root:
        tmp = Path(root)
        fake = tmp / "ffmpeg.exe"
        fake.write_text("x")
        inst = _installer(tmp)
        inst._settings.update({"ffmpeg_path": str(fake), "ffprobe_path": str(fake)})
        with patch("application.runtime_installer.sys.platform", "win32"), patch(
            "application.runtime_installer.shutil.which", return_value="winget"
        ), patch("application.runtime_installer.probe_host", return_value={
            "ok": True, "platform": "Windows", "machine": "AMD64",
            "gpu_name": "RTX 2060 SUPER", "cuda_detected": True,
            "recommended_device": "cuda", "notes": [],
        }):
            # Force ready via resolve seeing configured file
            tasks = {t["id"]: t for t in inst.list_tasks()["tasks"]}
        if "ffmpeg_winget" in tasks:
            assert tasks["ffmpeg_winget"]["available"] is False


def test_run_task_rejects_second_while_running() -> None:
    with tempfile.TemporaryDirectory() as root:
        inst = _installer(Path(root))
        inst._job = {"id": "rvc_venv_cuda", "status": "running", "message": "…", "progress": 10}
        result = inst.run_task("ffmpeg_path_hint")
        assert result.get("ok") is False
        assert "进行中" in str(result.get("error") or "")


if __name__ == "__main__":
    test_resolve_prefers_configured_path()
    test_list_tasks_disables_winget_when_ffmpeg_ready()
    test_run_task_rejects_second_while_running()
    print("ok")
```

- [ ] **Step 2: 跑测试，确认当前实现缺口（可能 fail）**

Run:

```bash
cd app && python test_runtime_installer.py
```

Expected: 至少 `test_list_tasks_disables_winget_when_ffmpeg_ready` 或 ready 判定与「假文件无 -version」相关项可能 FAIL——下一步修 `list_tasks` / `_ffmpeg_ready` 与检测边界。

说明：若 `_ffmpeg_ready` 仅看文件存在，测试可过；若与 `RuntimeService` 的 version 检测不一致，**以「路径文件存在 + list_tasks available」为准先过测试**，version 仍由组件表负责。

- [ ] **Step 3: 最小实现调整**

在 `runtime_installer.py` 的 `list_tasks` 中保证：

1. `ffmpeg_ok = self._ffmpeg_ready()`（基于 `_resolve_ffmpeg_paths()`）。
2. `ffmpeg_winget.available = (not ffmpeg_ok) and bool(shutil.which("winget"))` 且仅 `win32`。
3. `rvc_venv_cuda.available = (not rvc_ready) and profile.get("cuda_detected")`，其中 `rvc_ready` 来自：

```python
def _rvc_ready(self) -> bool:
    status = self._runtime.check_component("rvc")
    return status.get("status") == "ready"
```

4. `rvc_venv_cpu.available = (not rvc_ready) and not profile.get("cuda_detected")`（Win/通用兜底）。
5. `ffmpeg_path_hint`：`available=True`，label 保持「检测并绑定 ffmpeg」。
6. `run_task`：若 `_job.status == "running"`，**所有** task_id（含 `ffmpeg_path_hint`）均拒绝——与测试一致。

`detect_ffmpeg` 已返回 status 快照则保留；确保 `ok: false` 时有明确 `error` 字符串。

- [ ] **Step 4: 再跑测试**

```bash
cd app && python test_runtime_installer.py
```

Expected: 打印 `ok`，无 traceback。

- [ ] **Step 5: Commit**

```bash
git add app/application/runtime_installer.py app/test_runtime_installer.py app/api/bridge.py
git commit -m "$(cat <<'EOF'
feat: Runtime 安装任务与 ready 状态联动

问题：ffmpeg/rvc 安装任务 available 与检测结果脱节，进行中仍可触发冲突操作。

修复思路：list_tasks 按 _ffmpeg_ready/_rvc_ready 控制 winget/CUDA venv；
run_task 安装中统一拒绝；补 test_runtime_installer。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `/runtime` 就绪清单信息架构

**Files:**
- Modify: `web/src/pages/Runtime.tsx`
- Modify: `web/src/api/types.ts`（仅当任务/状态类型需扩展时）

**Interfaces:**
- Consumes: `api.getHostProfile`, `getRuntimeStatus`, `listRuntimeInstallTasks`, `runRuntimeInstallTask`, `getRuntimeInstallStatus`, `readRuntimeInstallLog`, `setRuntimePaths`, `checkRuntimeComponent`
- Produces: 页面区块 ①本机 ②就绪清单 ③进度 ④组件表 ⑤高级路径（折叠）

- [ ] **Step 1: 在 Runtime.tsx 增加就绪清单数据推导**

在组件内（`status` / `tasks` 已有）增加：

```tsx
const ffmpegStatus = status?.components.find((c) => c.key === 'ffmpeg')
const rvcStatus = status?.components.find((c) => c.key === 'rvc')
const taskById = Object.fromEntries(tasks.map((t) => [t.id, t]))

const readiness = [
  {
    key: 'ffmpeg',
    title: 'ffmpeg（必需）',
    status: ffmpegStatus?.status ?? 'missing',
    message: ffmpegStatus?.message ?? '未检测',
    primaryTaskId: taskById.ffmpeg_winget?.available
      ? 'ffmpeg_winget'
      : 'ffmpeg_path_hint',
    primaryLabel: taskById.ffmpeg_winget?.available ? '安装 ffmpeg' : '检测并绑定',
  },
  {
    key: 'rvc',
    title: 'RVC（必需）',
    status: rvcStatus?.status ?? 'missing',
    message: rvcStatus?.message ?? '未检测',
    primaryTaskId: taskById.rvc_venv_cuda?.available
      ? 'rvc_venv_cuda'
      : taskById.rvc_venv_cpu?.available
        ? 'rvc_venv_cpu'
        : '',
    primaryLabel: taskById.rvc_venv_cuda?.available
      ? '安装 RVC（CUDA）'
      : taskById.rvc_venv_cpu?.available
        ? '安装 RVC（CPU）'
        : '已就绪或请手填路径',
  },
]
```

- [ ] **Step 2: 渲染「就绪清单」卡片（放在本机摘要与可选安装之间）**

```tsx
<Card title="就绪清单（先完成这两项）" size="small">
  <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
    混音依赖 ffmpeg；翻唱推理依赖 RVC。UVR / So-VITS-SVC 可在下方手填路径（本页不提供一键安装）。
  </Typography.Paragraph>
  {readiness.map((row) => (
    <div key={row.key} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
      <div>
        <Space>
          <Typography.Text strong>{row.title}</Typography.Text>
          <Tag color={STATUS_COLOR[row.status as RuntimeStatusValue] ?? 'default'}>{row.status}</Tag>
        </Space>
        <div><Typography.Text type="secondary">{row.message}</Typography.Text></div>
      </div>
      <Button
        type="primary"
        size="small"
        disabled={installBusy || !row.primaryTaskId || row.status === 'ready'}
        loading={installingId === row.primaryTaskId}
        onClick={() => row.primaryTaskId && runInstall(row.primaryTaskId)}
      >
        {row.status === 'ready' ? '已完成' : row.primaryLabel}
      </Button>
    </div>
  ))}
</Card>
```

- [ ] **Step 3: 高级路径折叠**

将「运行环境路径」`Card` 改为：

```tsx
<Card title="高级：手动路径" size="small">
  <Collapse
    items={[{
      key: 'paths',
      label: '已有自建环境时展开填写',
      children: (
        <>
          <Form form={form} layout="vertical">
            {PATH_FIELDS.map(([key, label]) => (
              <Form.Item key={key} name={key} label={label}>
                <Input
                  allowClear
                  disabled={installBusy}
                  addonAfter={
                    <Button type="link" size="small" disabled={installBusy} onClick={() => choosePath(key)}>
                      选择
                    </Button>
                  }
                />
              </Form.Item>
            ))}
          </Form>
          <Button type="primary" onClick={save} loading={loading} disabled={installBusy}>
            保存并检测
          </Button>
        </>
      ),
    }]}
  />
</Card>
```

注意：从 `antd` 增加 `Collapse` import。

- [ ] **Step 4: 保留安装进度与全组件表；可选安装表可降为「其它任务」或保留在就绪清单下方**

确保 `installBusy` 仍禁用：所有安装按钮、保存、路径选择、组件重测、记住推荐设备。

- [ ] **Step 5: 前端构建**

```bash
cd web && npm run build
```

Expected: `tsc` 通过，vite build 成功。

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Runtime.tsx web/src/api/types.ts web/src/api/index.ts
git commit -m "$(cat <<'EOF'
feat: Runtime 就绪清单与高级路径折叠

问题：/runtime 任务列表平铺，用户难分清 ffmpeg+RVC 必达项与手填高级项。

修复思路：增加就绪清单主操作；路径区折叠为高级；保留进度条与全局禁用。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 安装反馈与 Create 默认设备串联

**Files:**
- Modify: `web/src/pages/Runtime.tsx`（`runInstall` 对同步任务的反馈）
- Modify: `web/src/pages/Create.tsx`（确认 HostProbe 默认 device，已有则补强）
- Modify: `README.md`

**Interfaces:**
- Consumes: `runRuntimeInstallTask` 同步返回 `{ ok, message, error, components?, paths? }`
- Produces: 用户可见 success/error；Create `params.device` 默认 `cuda`（Win+NVIDIA）

- [ ] **Step 1: 确认 `runInstall('ffmpeg_path_hint')` 分支**

必须包含：

- `setInstallingId` loading  
- `ok: false` → `message.error(error)`  
- `ok: true` → 若有 `components`+`paths` 则 `setStatus` + `form.setFieldsValue`，否则 `refresh()`  
- `message.success(message)`  
- `finally` 清 `installingId`  

长任务继续 `startInstallPoll`，间隔 ≤ 1000ms，并轮询 log。

- [ ] **Step 2: Create 默认设备**

在 `Create.tsx` 的 `useEffect` 中（已有 `getHostProfile` 则核对）：

```tsx
api.getHostProfile().then((p) => {
  if (!p?.recommended_device) return
  const cur = form.getFieldValue(['params', 'device'])
  if (!cur || cur === 'auto') {
    form.setFieldValue(['params', 'device'], p.recommended_device)
  }
}).catch(() => undefined)
```

- [ ] **Step 3: 更新 README「Windows 快速验收」**

对齐 spec 步骤：

1. `/runtime` 本机摘要见 GPU + **cuda**  
2. 就绪清单：检测/安装 ffmpeg → ready  
3. 就绪清单：安装 RVC（CUDA）→ ready  
4. `/models` 导入 → `/create` 设备 cuda → 立即开始  

写明：UVR/SVC 手填；日志 `runtime_install.log`。

- [ ] **Step 4: 构建与 py_compile**

```bash
python3 -m py_compile app/application/runtime_installer.py app/application/runtime_service.py app/api/bridge.py
cd web && npm run build
cd ../app && python test_runtime_installer.py
```

Expected: 全部成功。

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Runtime.tsx web/src/pages/Create.tsx README.md
git commit -m "$(cat <<'EOF'
fix: Runtime 同步检测反馈与 Win 验收文档

问题：检测绑定反馈弱；文档与就绪清单主路径不一致。

修复思路：强化 ffmpeg_path_hint 即时 UI；Create 继承推荐 device；README Win 步骤对齐 spec。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 真机验收清单（人工，不写代码）

**Files:** 无代码；可选在 PR/回复中勾选。

- [ ] **Step 1: Win 2060S 手工验收**

| # | 操作 | 期望 |
|---|------|------|
| 1 | 打开桌面应用 `/runtime` | 本机摘要显示 NVIDIA，推荐 **cuda** |
| 2 | 就绪清单点 ffmpeg 安装或检测 | 成功 message；组件 ffmpeg **ready**；winget 项不可再装 |
| 3 | 点 RVC CUDA 安装 | 进度/日志有更新；结束后 rvc **ready**；`rvc_python` 已填 |
| 4 | 安装进行中乱点其它按钮 | 全部 disabled |
| 5 | `/models` 导入 RVC → Create | 默认 device **cuda** |
| 6 | start_work（可用 vocals 短音频） | 不出现「rvc runtime 未就绪」 |

- [ ] **Step 2: 失败路径抽查**

- 未装 winget 时 winget 任务不可用或错误可读  
- 检测绑定在无 ffmpeg 时 error 明确  

- [ ] **Step 3: 收尾**

```bash
git status
git push origin main   # 若用户要求推送
```

---

## Spec coverage (self-review)

| Spec 要求 | Task |
|-----------|------|
| HostProbe Win+cuda | T3 Create + 已有 probe；T4 验收 |
| ffmpeg/rvc ready | T1 available + T2 清单 + T4 |
| 可选安装用户确认 | T1/T2（按钮触发） |
| `/runtime` 五区块 | T2 |
| 安装中全局禁用 | T2（沿用 installBusy） |
| 同步 detect 反馈 | T3 |
| 不改 WorkService 流水线 | 全任务未改 work_service |
| 不做 UVR/SVC 一键装 | T2 文案标明手填 |
| 测试 | T1 `test_runtime_installer.py` |
| README | T3 |

**Placeholder scan:** 无 TBD。  
**类型一致性:** task id 与现网 `ffmpeg_winget` / `ffmpeg_path_hint` / `rvc_venv_cuda` / `rvc_venv_cpu` 一致。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-09-runtime-env-foundation.md`.

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每任务新开 subagent，任务间我复核  
2. **Inline Execution** — 本会话按 executing-plans 连续做完并设检查点  

要我 **commit 本 plan 文件** 并开始执行的话，回复 **1** 或 **2**（或「先 push 文档再执行」）。

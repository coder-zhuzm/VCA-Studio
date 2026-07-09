# Runtime 环境基础（Win 优先）设计

> 日期：2026-07-09  
> 状态：待用户审阅后进入 implementation plan  
> 相关：`VCA_IMPLEMENTATION_ROADMAP.md` §3 / §10.3、`docs/superpowers/specs/2026-07-06-runtime-manager-design.md`（检测切片）、当前 `runtime_service` / `runtime_installer` / `Runtime.tsx`

---

## 1. Goal

在 **Windows 优先**（目标机：i5-12400 + RTX 2060 SUPER）前提下，把 **运行环境** 打成可用基础，使用户在 **`/runtime` 自助** 完成：

1. **`ffmpeg` = ready**（混音、输入规范化等依赖）
2. **`rvc` = ready**（CUDA 优先的 RVC 推理环境）
3. **`start_work` 不因 runtime 未就绪被拦**（路径已配置且检测通过时）

本设计是对 2026-07-06 Runtime Manager「仅检测」切片的 **能力升级**，并收敛当前零散可选安装实现，对齐路线图：

```text
软件安装器  ≠  运行环境管理
手动路径接入 → 可选在线安装/修复 →（以后）整合包扫描
```

---

## 2. Scope

### 2.1 In scope（本轮）

| 项 | 说明 |
|----|------|
| 本机探测 | OS / NVIDIA GPU / 推荐推理设备 `cuda`（无 GPU 则 `cpu`） |
| 深度检测 | 以 `RuntimeService` 为真相源：`ready \| partial \| missing \| error` |
| 可选安装（用户确认才执行） | Win：`ffmpeg`（winget 或检测绑定）、`rvc`（CUDA venv） |
| `/runtime` 信息架构 | 本机摘要 → 就绪清单 → 安装进度 → 全组件表 → 高级手填路径 |
| 安装 UX | 实时进度与日志；安装进行中全局禁用冲突操作 |
| 与 Create | 默认设备跟随推荐；不改推理/混音流水线 |

### 2.2 Out of scope（本轮明确不做）

| 项 | 原因 |
|----|------|
| 首次强制向导 / 全局拦截 Create | 产品选择：自助 `/runtime` |
| UVR / SVC **一键安装** | 范围 A：仅检测 + 手动路径 |
| 整合包目录扫描、底模下载 | 路线图后续 |
| Windows 软件安装包（Inno 等） | 与 Runtime 分离 |
| 环境冒烟 / 端到端试跑按钮 | 验收标准选「组件 ready 即可」 |
| Mac 一键装齐为主路径 | 兼容保留，不挡 Win |

### 2.3 Success criteria（可测）

- [ ] Win 上 HostProbe 能识别 NVIDIA，推荐设备为 **`cuda`**
- [ ] 用户可完成 ffmpeg 安装或检测绑定，组件 **ffmpeg = ready**
- [ ] 用户可完成 RVC CUDA venv（或手填可用 `rvc_python`），组件 **rvc = ready**
- [ ] Create 选择 RVC 模型后 `start_work` 通过环境校验（不出现 rvc runtime 未就绪）
- [ ] 安装进行中不可重复点安装/改路径；结束后状态刷新正确
- [ ] ffmpeg 已 ready 时，winget 安装任务不可再点（「已完成」）

---

## 3. Architecture

### 3.1 Layers

```text
Runtime.tsx
  · 展示与用户确认，不写安装实现
        │
        ▼ bridge
RuntimeInstaller
  · list_tasks / run_task / 进度与日志
  · 成功后写 SettingsStore
        │
        ▼ 查询
RuntimeService
  · status / check_component / set_paths（检测真相源）
        │
HostProbe
  · platform / gpu / recommended_device
```

### 3.2 Capability vs Install Task

| 概念 | 定义 | 本轮 |
|------|------|------|
| **Capability** | 某组件当前是否可用（检测结果） | 必达：`ffmpeg`、`rvc`；旁路：`uvr`、`svc` 仅检测 |
| **Install Task** | 用户触发的一次安装/绑定动作 | 见 §5 |

**规则：**

- 安装是否 `available` 由 **检测结果 + 平台** 决定，不以「任务列表写死 always true」为主。
- 安装成功只负责 **写路径**；是否 ready **必须再经 RuntimeService 检测**。

### 3.3 Data flow（Win 主路径）

```text
打开 /runtime
  → HostProbe + RuntimeService.status()
  → 就绪清单：ffmpeg? rvc?

用户确认安装/检测
  → Installer 后台任务 + 流式 message/progress + runtime_install.log
  → 写 ffmpeg_path / rvc_python 等
  → status 刷新 → ready

Create / start_work
  → 现有 _start_blocker：按 model.framework 查 rvc/svc
  → 混音路径继续依赖已配置 ffmpeg
```

### 3.4 Relation to existing code

| 模块 | 处理 |
|------|------|
| `runtime_service.py` | 保留为检测真相源；可小补文案/检查项，不改 status 形状语义 |
| `runtime_installer.py` | 收敛任务：available 与 ready 联动；Win 主路径清晰；流式进度保留 |
| `host_probe.py` | 保留；Win+NVIDIA → cuda |
| `Runtime.tsx` | 按 §4 重组信息架构 |
| `WorkService` | **不改**流水线，只保证环境 ready 后现有校验可通过 |

---

## 4. `/runtime` information architecture

自上而下：

| 区块 | 内容 | 行为 |
|------|------|------|
| **① 本机摘要** | 系统、GPU、驱动、推荐设备 | 「记住推荐设备」；Create 可读推荐 device |
| **② 就绪清单（核心）** | 突出 `ffmpeg`、`rvc`；UVR/SVC 标注「可选·手填」 | 状态色 + 人话说明 + 主操作（检测/安装/已完成） |
| **③ 安装进度** | 仅 running 或刚结束时 | 进度条、message、日志尾；**进行中全局禁用** |
| **④ 全部组件表** | 五组件 + checks 明细 | 单组件重测；安装中禁用 |
| **⑤ 高级：手动路径** | 七个 path 字段 | 建议默认折叠；「保存并检测」 |

新用户应只依赖 ①② 完成环境；⑤ 服务已有自建环境用户。

---

## 5. Detection rules（P0）

| 组件 | ready 条件 |
|------|------------|
| **ffmpeg** | 配置路径或 PATH/常见路径存在，且 `ffmpeg -version` 成功；尽量绑定同目录 `ffprobe` |
| **ffprobe** | 路径存在且 version 成功（可与 ffmpeg 同源） |
| **rvc** | `rvc_python` 为可执行文件，且 `import torch`、`import rvc_python` 成功 |
| **svc** | 现有：python + repo `infer_tool` + 关键 import（本轮不装） |
| **uvr** | 现有：python + model dir + 模型文件（本轮不装） |

路径解析（ffmpeg 绑定）至少覆盖：

- settings 中已配置路径  
- `shutil.which("ffmpeg")`  
- Win 常见位置（若可稳定探测）  
- Mac 兼容：`/opt/homebrew/bin`、`/usr/local/bin`（不挡 Win）

---

## 6. Install tasks（Windows 优先）

| task id | available 条件 | 行为 | 成功 |
|---------|----------------|------|------|
| `ffmpeg_winget` | ffmpeg **未** ready 且存在 winget | `winget install Gyan.FFmpeg`（用户确认） | resolve + 写 `ffmpeg_path`/`ffprobe_path` |
| `ffmpeg_path_hint` | 始终可点（文案：检测并绑定） | 不安装，只解析并写入路径 | 返回 status 快照；失败可读错误 |
| `rvc_venv_cuda` | rvc **未** ready 且 `cuda_detected` | 数据目录下 venv + CUDA 轮 torch + `rvc-python` | 写 `rvc_python` |
| `rvc_venv_cpu` | 无 CUDA 时兜底 | CPU torch + rvc-python | 写 `rvc_python` |

**并发：** 同时只允许一个安装 job；进行中禁用所有安装、路径保存、组件重测。

**日志：** `DATA_DIR/runtime_install.log`；UI 展示尾部行。

**失败文案最低要求：**

| 场景 | 提示方向 |
|------|----------|
| 无 winget | 手装 ffmpeg 或手动填路径 |
| winget/pip 非 0 | 指向 log + 摘要 |
| CUDA venv 但 torch.cuda 不可用 | 警告驱动/轮子；可暂用 cpu |
| 检测绑定找不到 ffmpeg | 明确未找到，引导 winget 或手填 |

---

## 7. Bridge / API surface

保持并规范现有能力：

```text
get_host_profile()
get_runtime_status()
check_runtime_component(key)
set_runtime_path / set_runtime_paths
list_runtime_install_tasks()
run_runtime_install_task(task_id)
get_runtime_install_status()
read_runtime_install_log()
```

约定：

- `run_runtime_install_task("ffmpeg_path_hint")` **同步**返回绑定结果，并尽量带上 `components` + `paths`（避免「点了没反应」）。
- 长任务（winget / venv）走后台 job + 轮询。

---

## 8. Create / WorkService 衔接

- Create 默认 `params.device`：有 HostProbe 推荐则采用（Win+NVIDIA → `cuda`）。
- **不修改** `_run_work` / 混音算法；仅保证环境 ready 后现有 `_start_blocker` 可通过。
- stems/song 混音仍依赖已配置 ffmpeg（现有校验保留或沿用）。

---

## 9. Error handling

- 检测：不抛到 UI；组件 status + message。
- 安装：job `failed` + message；log 落盘。
- 非法 task id：`{ ok: false, error }`。
- 前端：所有 run 结果必须有 success 或 error 的 **即时反馈**（message），禁止静默。

---

## 10. Testing / verification

最低：

```bash
python3 -m py_compile app/application/runtime_service.py app/application/runtime_installer.py app/application/host_probe.py app/api/bridge.py
npm run build --prefix web
```

建议补（实现阶段）：

- ffmpeg 路径解析：假路径 / which / 常见路径  
- `list_tasks`：ffmpeg ready 后 winget 任务 `available=false`  
- 安装中 `run_task` 第二次调用拒绝  

真机（Win 2060S）手工：

1. `/runtime` 见 GPU + cuda  
2. 检测/安装 ffmpeg → ready  
3. RVC CUDA venv → ready  
4. 导入模型 → Create → start_work 过环境校验  

---

## 11. Implementation order（供 plan 拆分）

1. 收敛 Installer：available 与 ready 联动 + ffmpeg 解析统一  
2. Runtime.tsx 区块化（就绪清单 + 进度 + 高级折叠）  
3. 安装反馈：同步任务即时 message；长任务 轮询间隔与禁用  
4. HostProbe / Create 默认 device 串联验收  
5. 文档：更新 README Runtime 节与路线图「环境基础」一句  

---

## 12. Non-goals reminder

不做完整 install.py 复刻、不做整合包扫描、不做 UVR/SVC 一键装、不做强制 onboarding。后续可在本架构上扩展 capability 与 task，而无需推翻 `/runtime`。

# VCA-Studio

VCA-Studio 是桌面级 **AI 翻唱编排工作台**：单模型翻唱、多模型混唱、片段时间轴、局部重渲染与原唱解析 MVP 已接入后端；详细阶段说明见 [VCA_IMPLEMENTATION_ROADMAP.md](./VCA_IMPLEMENTATION_ROADMAP.md)。

## 当前进度（2026-07-09）

**后端**：P0 单模型闭环、So-VITS-SVC 双引擎、P1 多模型整轨推理 + 拼接、合唱/limiter、`rerender_work`（缺缓存时按片段指派补推理）、UVR 分离（可降级）、模型链接/ZIP 导入、音高解析与歌词对齐 API 均已落地。

**前端**：Runtime / 模型 / 新建翻唱（单模型）/ 作品库 / 时间轴编辑（`/editor/:id`）/ 原唱解析面板 / 从链接导入模型。

**需在真机配置 Runtime 后验收**：RVC、SVC、UVR、ffmpeg 路径正确时，`start_work` 会走分离 → 推理 → 混音并写出 `output/final.wav`。

### 已实现能力摘要

- ✅ React + Vite + TypeScript + Ant Design + pywebview + bridge + mock fallback
- ✅ JSON 存储、`/runtime` 深度检测（ffmpeg / SVC / RVC / UVR）
- ✅ `/models` 本地导入 + **从 http(s)/file 链接或 ZIP 导入**
- ✅ `/create` 三种输入模式、RVC 参数、可选输入 WAV 规范化
- ✅ `/works` 列表、详情、步骤、进度、日志、重试、导出、打开目录
- ✅ 后台**串行任务队列**执行 `start_work`
- ✅ `/editor/:id` 片段表编辑、保存时间轴、局部/整轨重渲染、原唱解析
- ✅ 多模型 + `segments`：**API/`create_work` 已支持**；创建页 UI 仍以单模型为主

### 已知缺口（产品层）

- `/create` 未提供 LRC 导入与多模型编排 UI（可手工调 API 或后续补 UI）
- `/works` 无自动轮询进度，需手动刷新；应用内成品/干声试听未做
- 侧栏「时间轴编辑」指向 `/editor`，有效入口为作品库「编辑」→ `/editor/:id`
- 完整多轨波形编辑器、在线曲库、ModelScope 全站、自动安装器、Guide Singer 仍后置

## 已有页面

| 路由 | 状态 | 说明 |
|---|---|---|
| `/` | 已实现 | 应用状态、数据目录、最近作品 |
| `/runtime` | 已实现 | 路径保存、深度检测、单组件重测 |
| `/models` | 已实现 | 本地导入、检查、链接导入 |
| `/create` | 已实现 | 创建 work；单模型表单 |
| `/works` | 已实现 | 作品库与管理流 |
| `/editor/:id` | 已实现 | 时间轴编辑、重渲染、原唱解析 |

## 本地启动

### 1. 准备环境

- Python 3.10+
- Node.js 20.19+
- Git

### 2. 安装并构建前端

```powershell
cd web
npm install
npm run build
```

### 3. 启动桌面应用（生产模式）

```powershell
cd ..\app
pip install pywebview
python main.py
```

### 4. 开发模式启动

终端 1：

```powershell
cd web
npm install
npm run dev
```

终端 2：

```powershell
cd app
pip install pywebview
python main.py --dev
```

开发模式桌面壳加载 `http://localhost:5173?desktop=1`；浏览器直连 `http://localhost:5173` 使用 mock API。

## Runtime Manager

`/runtime` 为**手动路径 + 检测**，不自动安装完整 AI runtime。

| Key | 说明 |
|---|---|
| `ffmpeg_path` / `ffprobe_path` | 留空则尝试 PATH |
| `svc_python` / `sovits_repo` | So-VITS-SVC |
| `rvc_python` | RVC |
| `uvr_python` / `uvr_model_dir` | UVR 分离 |

## 作品流水线（`start_work`）

| 模式 | 行为 |
|---|---|
| `song` | UVR 分离（失败可降级为人声=原曲）→ 推理 → 有伴奏则混音 |
| `vocals` / `stems` | 使用已准备人声 → 推理；`stems` 可与伴奏混音 |
| 含 `segments` | 各模型整轨推理 → 裁切拼接（含 choir/mute/original）→ 混音 |

作品目录见路线图：`.vca_studio/works/<id>/`（`input/`、`stems/`、`renders/`、`inference/`、`output/`、`run.log`）。

## 技术结构

```text
VCA-Studio/
├─ app/
│  ├─ api/bridge.py
│  ├─ application/          # work, model, runtime, lrc, stitch, stem_preparer, …
│  ├─ infrastructure/       # rvc/svc engine, uvr, pitch, model_downloader, …
│  └─ main.py
├─ web/src/pages/           # Home, Runtime, Models, Create, Works, Editor
├─ VCA_IMPLEMENTATION_ROADMAP.md
├─ PROJECT_COPY_REPORT.md   # 参考项目对齐清单（§10 已与 2026-07-09 代码同步）
└─ README.md
```

## 本地数据目录

环境变量 `VCA_DATA_DIR` 可覆盖默认路径（Windows `%APPDATA%/VCA-Studio/.vca_studio` 等）。

## 后续优先（对齐路线图）

1. Create：LRC + 多模型 UI  
2. Works：运行中轮询 + 试听  
3. 真机全链路验收（RVC/SVC/UVR）  
4. Guide Singer、波形多轨编辑器、在线曲库（后置）

## 参考项目

功能规划参考 [SDIJF1521/xb-svcb](https://github.com/SDIJF1521/xb-svcb)。本仓库 MIT，使用第三方模型与 runtime 请遵守各自许可。
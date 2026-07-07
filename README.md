# VCA-Studio

VCA-Studio 是开发中的桌面级 AI 翻唱工作台。当前目标是先跑通 P0 单模型 RVC 翻唱闭环，再扩展多模型混唱、时间轴和音频编辑器。

## 当前进度

已完成 **桌面基础壳 + Runtime Manager + ModelService + WorkService P0 管理流**。

- ✅ React + Vite + TypeScript 前端骨架
- ✅ Ant Design 基础布局
- ✅ pywebview 桌面壳
- ✅ 前后端 bridge：`window.pywebview.api.*`
- ✅ 浏览器开发环境 mock fallback
- ✅ JSON 本地存储：`settings.json` / `models.json` / `works.json`
- ✅ Windows / macOS / Linux 用户数据目录基础适配
- ✅ 生产模式加载 `web/dist/index.html`
- ✅ `/runtime` 运行环境页面：路径保存、深度检测、单组件重测
- ✅ ffmpeg / ffprobe 执行检测
- ✅ SVC / RVC / UVR Python import 检测
- ✅ UVR 模型目录与模型文件检测
- ✅ pywebview 文件 / 目录选择器
- ✅ `/models` 本地模型管理：导入、检查、删除、默认模型、打开目录
- ✅ RVC / So-VITS-SVC 模型文件复制到数据目录
- ✅ `/create` 新建作品：三种输入模式、模型选择、RVC 参数、文件选择
- ✅ `StemPreparer`：`song` / `vocals` / `stems` 输入复制；配置 ffmpeg 时转 44100Hz WAV
- ✅ `/works` 作品库：列表、详情、日志、步骤、进度、重命名、删除、重试、导出、打开目录/日志
- ✅ work 目录写入 `work.json` 和 `run.log`
- ✅ 首页显示最近作品和数据目录入口

当前还不能执行真实 AI 翻唱：RVC/SVC 推理、UVR 分离、混音仍未接入。`start_work` 会做前置校验，随后以“真实 RVC 推理尚未接入”失败收口。

## 已有页面

| 路由 | 状态 | 说明 |
|---|---|---|
| `/` | 已实现 | 应用状态、数据目录、最近作品 |
| `/runtime` | 已实现 | runtime 路径保存、深度检测、单组件重测 |
| `/models` | 已实现 | 本地 RVC / So-VITS-SVC 模型导入与管理 |
| `/create` | 已实现 P0 表单 | 创建 work 记录，准备输入文件 |
| `/works` | 已实现管理流 | 作品列表、详情、日志、重试、导出、删除 |

## 本地启动

### 1. 准备环境

需要先安装：

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

开发模式需要两个终端。

终端 1：启动 Vite：

```powershell
cd web
npm install
npm run dev
```

终端 2：启动 pywebview：

```powershell
cd app
pip install pywebview
python main.py --dev
```

开发模式下桌面壳会加载：

```text
http://localhost:5173?desktop=1
```

普通浏览器直接打开 `http://localhost:5173` 时会使用 mock API。

## Runtime Manager 当前能力

`/runtime` 页面用于接入用户已有的本地 AI 运行环境。当前只做 **手动路径 + 检测**，不自动安装。

### 可配置路径

| Key | 说明 |
|---|---|
| `ffmpeg_path` | ffmpeg 可执行文件路径；留空时尝试 PATH |
| `ffprobe_path` | ffprobe 可执行文件路径；留空时尝试 PATH |
| `svc_python` | So-VITS-SVC 推理环境 Python |
| `sovits_repo` | so-vits-svc 仓库目录 |
| `rvc_python` | RVC 推理环境 Python |
| `uvr_python` | UVR 分离环境 Python |
| `uvr_model_dir` | UVR 模型目录 |

### 检测规则

| 组件 | 当前检测 |
|---|---|
| ffmpeg | 路径存在，并能执行 `ffmpeg -version` |
| ffprobe | 路径存在，并能执行 `ffprobe -version` |
| SVC | `svc_python` 存在；`torch` / `librosa` / `fairseq` 可 import；`sovits_repo/inference/infer_tool.py` 存在 |
| RVC | `rvc_python` 存在；`torch` / `rvc_python` 可 import |
| UVR | `uvr_python` 存在；`audio_separator` 可 import；UVR 模型目录和默认模型文件存在 |

当前不做：自动安装 runtime、整合包扫描、CUDA/GPU 深度检测、模型下载。

## 模型管理当前能力

`/models` 页面支持本地导入 RVC 与 So-VITS-SVC 模型。导入时会把模型文件复制到数据目录，后续流程不依赖原始外部路径。

| Framework | 必填 | 可选 |
|---|---|---|
| RVC | `.pth` | `.index` |
| So-VITS-SVC | `.pth`, `config.json` | diffusion `.pt`, diffusion config `.yaml/.yml` |

已支持：文件选择器、导入、检查、删除、设置默认、打开模型目录。

## WorkService 当前能力

`/create` 创建 work 后会：

1. 校验模型存在
2. 复制输入文件到 `works/<work_id>/input/`
3. 配置 ffmpeg 时转成 44100Hz WAV
4. 写入 `works.json`
5. 写入 `works/<work_id>/work.json`
6. 写入 `works/<work_id>/run.log`

支持输入类型：

| 模式 | 输入 | 当前行为 |
|---|---|---|
| `song` | 完整歌曲 | 准备输入；真实 UVR 分离未接入 |
| `vocals` | 已分离人声 | 准备输入；可进入 RVC 前置校验 |
| `stems` | 已分离人声 + 伴奏 | 准备输入；混音未接入 |

作品库已支持：列表、最近作品、状态、进度、步骤、日志、重命名、失败重试、删除、打开目录、打开日志、导出已有 `output/final.wav`。

## 技术结构

```text
VCA-Studio/
├─ app/                         # Python 桌面壳 + bridge + 本地服务
│  ├─ api/bridge.py             # pywebview JS API
│  ├─ application/model_service.py
│  ├─ application/runtime_service.py
│  ├─ application/stem_preparer.py
│  ├─ application/work_service.py
│  ├─ infrastructure/storage.py # JSON storage
│  ├─ config.py                 # 应用信息、路径、数据目录
│  └─ main.py                   # pywebview 入口
├─ web/                         # React + Vite 前端
│  └─ src/
│     ├─ api/                   # bridge wrapper + 类型
│     ├─ pages/                 # P0 页面
│     ├─ App.tsx
│     └─ main.tsx
├─ docs/superpowers/            # 设计与实施计划
├─ VCA_IMPLEMENTATION_ROADMAP.md
├─ PROJECT_COPY_REPORT.md
├─ README.md
└─ LICENSE
```

## 本地数据目录

支持 `VCA_DATA_DIR` 环境变量覆盖。

默认路径：

| 平台 | 默认路径 |
|---|---|
| Windows | `%APPDATA%/VCA-Studio/.vca_studio` |
| macOS | `~/Library/Application Support/VCA-Studio/.vca_studio` |
| Linux | `$XDG_DATA_HOME/VCA-Studio/.vca_studio` 或 `~/.local/share/VCA-Studio/.vca_studio` |

当前会写入：

```text
settings.json
models.json
models/
works.json
works/<work_id>/input/
works/<work_id>/run.log
works/<work_id>/work.json
```

## P0 剩余任务

1. **UVR 分离**：`song` 模式接入真实人声 / 伴奏分离
2. **InferenceRunner**：真实调用 RVC；SVC 推理后置到 P1/P2
3. **MixService**：有伴奏则混音，无伴奏输出 AI 干声
4. **串行任务队列**：后台执行，避免阻塞 UI
5. **试听**：成品 / AI 干声 / 伴奏预览
6. **导出增强**：真实输出生成后导出 WAV；MP3 后置

## P0 暂不做

- 在线曲库
- ModelScope 模型站
- 多模型混唱
- 音频编辑器
- 自动安装完整 AI runtime
- Mac 安装包 / Windows 安装器

## 参考项目

本项目功能规划参考：

- [SDIJF1521/xb-svcb](https://github.com/SDIJF1521/xb-svcb)

VCA-Studio 会复用其产品经验和部分架构思路，例如 Python + pywebview、本地 JSON 存储、ffmpeg、UVR、RVC/SVC 子环境、作品库与任务队列。

首版刻意保持小范围：先实现核心翻唱闭环，再扩展多模型、编辑器和生态能力。

## 开源协议

本仓库使用 MIT License，详见 [LICENSE](./LICENSE)。

参考项目 `xb-svcb` 的源码、模型、依赖和第三方服务可能有各自协议与限制。使用、复刻或分发相关能力时，请同时遵守原项目和对应依赖的许可证要求。

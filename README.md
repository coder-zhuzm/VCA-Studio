# VCA-Studio

VCA-Studio 是一个开发中的桌面级 AI 翻唱工作台。项目规划参考 [xb-svcb](https://github.com/SDIJF1521/xb-svcb)，当前已支持桌面壳、运行环境路径管理与轻量检测，后续逐步接入 SVC/RVC 推理、混音和作品工作流。

## 当前进度

当前已完成 **桌面基础壳 + Runtime Manager + ModelService 第一版**：

- ✅ React + Vite + TypeScript 前端骨架
- ✅ Ant Design 基础布局
- ✅ pywebview 桌面壳
- ✅ 前后端 bridge：`window.pywebview.api.*`
- ✅ 浏览器开发环境 mock fallback
- ✅ JSON 本地 settings 存储
- ✅ Windows / macOS / Linux 用户数据目录基础适配
- ✅ 生产模式加载 `web/dist/index.html`
- ✅ `/runtime` 运行环境页面
- ✅ ffmpeg / ffprobe / SVC / RVC / UVR 轻量状态检测
- ✅ 手动填写并保存 runtime 路径
- ✅ `/models` 本地模型管理第一版
- ✅ RVC / So-VITS-SVC 模型导入、检查、删除、默认模型

当前还不能执行真实 AI 翻唱；模型导入、音频准备、SVC/RVC 推理、混音、作品队列仍在后续阶段。

## 已有页面

| 路由 | 状态 | 说明 |
|---|---|---|
| `/` | 已有占位 | 首页 / 应用状态 |
| `/runtime` | 已实现第一版 | 运行环境路径保存与轻量检测 |
| `/models` | 已实现第一版 | 本地 RVC / So-VITS-SVC 模型导入与管理 |
| `/create` | 占位 | 后续创建翻唱任务 |
| `/works` | 占位 | 后续作品库、日志、导出 |

## Windows 本地启动

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

`/runtime` 页面用于先接入用户已有的本地 AI 运行环境。当前只做 **手动路径 + 轻量检测**。

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
| SVC | `svc_python` 文件存在；`sovits_repo/inference/infer_tool.py` 存在 |
| RVC | `rvc_python` 文件存在 |
| UVR | `uvr_python` 文件存在；`uvr_model_dir` 是目录 |

### 当前不做

- 不自动安装 runtime
- 不扫描整合包目录
- 不检测 CUDA / GPU
- 不检测 torch / fairseq / audio_separator import
- 不下载模型
- 不执行真实推理

这些会在核心闭环后续阶段逐步补齐。

## 模型管理当前能力

`/models` 页面支持本地导入 RVC 与 So-VITS-SVC 模型。导入时会把模型文件复制到数据目录，后续流程不依赖原始外部路径。

### 支持格式

| Framework | 必填 | 可选 |
|---|---|---|
| RVC | `.pth` | `.index` |
| So-VITS-SVC | `.pth`, `config.json` | diffusion `.pt`, diffusion config `.yaml/.yml` |

当前不做推理、zip 导入、ModelScope、文件选择器和深度依赖检测。

## 技术结构

```text
VCA-Studio/
├─ app/                         # Python 桌面壳 + bridge + 本地服务
│  ├─ api/bridge.py             # pywebview JS API
│  ├─ application/runtime_service.py
│  ├─ infrastructure/storage.py # JSON settings 存储
│  ├─ config.py                 # 应用信息、路径、数据目录
│  └─ main.py                   # pywebview 入口
├─ web/                         # React + Vite 前端
│  └─ src/
│     ├─ api/                   # bridge wrapper + 类型
│     ├─ pages/                 # P0 页面
│     ├─ App.tsx
│     └─ main.tsx
├─ docs/superpowers/            # 设计与实施计划
├─ PROJECT_COPY_REPORT.md       # 复刻规划报告
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
```

后续会继续加入：

```text
works.json
works/
temp/
```

## 后续规划

P0 目标是跑通 AI 翻唱核心闭环：

```text
配置运行环境
→ 导入 SVC/RVC 模型
→ 选择完整歌曲 / 已分离人声 / 人声+伴奏
→ 人声准备
→ SVC/RVC 推理
→ 有伴奏则混音
→ 导出结果
→ 日志可查、失败可重试
```

### P0 剩余任务

1. **StemPreparer**：支持 `song` / `vocals` / `stems` 三种输入模式
2. **InferenceRunner**：真实调用 SVC / RVC，不生成假结果
3. **MixService**：有伴奏则混音，无伴奏输出 AI 干声
4. **WorkService**：串行任务队列、状态、日志、失败重试
5. **导出**：WAV 必做，MP3 可选

### P0 暂不做

- 在线曲库
- ModelScope 模型站
- 多模型混唱
- 音频编辑器
- 自动安装完整 AI runtime
- Mac 安装包 / Windows 安装器

## 参考项目

本项目功能规划参考：

- [SDIJF1521/xb-svcb](https://github.com/SDIJF1521/xb-svcb)

VCA-Studio 会复用其产品经验和部分架构思路，例如：

- Python + pywebview 桌面壳
- 本地 JSON 存储
- ffmpeg 音频处理
- UVR 人声分离
- So-VITS-SVC / RVC 推理子环境
- 作品库与任务队列

但 VCA-Studio 首版会刻意保持更小范围：先实现核心翻唱闭环，再扩展多模型、编辑器和生态能力。

## 开源协议

本仓库使用 MIT License，详见 [LICENSE](./LICENSE)。

参考项目 `xb-svcb` 的源码、模型、依赖和第三方服务可能有各自协议与限制。使用、复刻或分发相关能力时，请同时遵守原项目和对应依赖的许可证要求。

# VCA-Studio

VCA-Studio 是一个面向 AI 翻唱工作流的桌面应用项目。当前项目参考并复刻自 [xb-svcb](https://github.com/SDIJF1521/xb-svcb)，但不会原样搬运全部功能；首要目标是先跑通更轻量、可维护的 **AI 翻唱核心闭环**。

## 当前状态

当前仓库已完成第一阶段基础骨架：

- ✅ React + Vite + TypeScript 前端骨架
- ✅ pywebview 桌面壳
- ✅ 前后端 bridge：`window.pywebview.api.*`
- ✅ 浏览器开发环境 mock fallback
- ✅ JSON 本地 settings 存储
- ✅ P0 页面占位：
  - 首页 `/`
  - 运行环境 `/runtime`
  - 模型管理 `/models`
  - 新建翻唱 `/create`
  - 作品库 `/works`
- ✅ 生产模式支持加载 `web/dist/index.html`
- ✅ Windows / macOS / Linux 用户数据目录基础适配

> 注意：当前还不能执行真实 AI 翻唱；SVC / RVC / UVR / ffmpeg 运行环境检测和推理链路还在后续阶段。

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

## 已实现功能

### 桌面壳

- 使用 `pywebview` 创建桌面窗口
- 开发模式加载 Vite dev server
- 生产模式加载 `web/dist/index.html`
- 支持 pywebview JS API 注入

### 前端

- React 19 + TypeScript + Vite
- Ant Design 基础布局
- React Router HashRouter，兼容 `file://` 生产模式
- 五个 P0 页面占位

### 本地存储

- JSON settings 存储
- 写入使用临时文件替换
- settings 读写有线程锁保护
- 支持 `VCA_DATA_DIR` 覆盖数据目录

默认数据目录：

| 平台 | 默认路径 |
|---|---|
| Windows | `%APPDATA%/VCA-Studio/.vca_studio` |
| macOS | `~/Library/Application Support/VCA-Studio/.vca_studio` |
| Linux | `$XDG_DATA_HOME/VCA-Studio/.vca_studio` 或 `~/.local/share/VCA-Studio/.vca_studio` |

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

计划顺序：

1. Runtime Manager：检测 ffmpeg / SVC / RVC / UVR，并保存用户选择路径
2. ModelService：导入本地 So-VITS-SVC / RVC 模型
3. StemPreparer：支持 `song` / `vocals` / `stems` 三种输入模式
4. InferenceRunner：真实调用 SVC / RVC，不生成假结果
5. MixService：有伴奏则混音，无伴奏输出 AI 干声
6. WorkService：串行任务队列、状态、日志、失败重试
7. 导出：WAV 必做，MP3 可选

暂不作为 P0：

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

但 VCA-Studio 首版会刻意保持更小范围：先实现核心翻唱闭环，再扩展生态功能。

## 开源协议

本仓库使用 MIT License，详见 [LICENSE](./LICENSE)。

参考项目 `xb-svcb` 的源码、模型、依赖和第三方服务可能有各自协议与限制。使用、复刻或分发相关能力时，请同时遵守原项目和对应依赖的许可证要求。

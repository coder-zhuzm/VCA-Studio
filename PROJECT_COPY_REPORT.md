# VCA-Studio 项目复刻完整报告

> 新项目仓库名：**VCA-Studio**。  
> 目标：参考当前 XB-SVCB 项目，实现以 **AI 翻唱核心闭环** 为优先的新项目，并后续新增 **Mac 客户端**。  
> 当前参考项目版本：`0.0.14`，见 `app/pyproject.toml`、`web/package.json`、`app/config.py`。

---

## 1. 产品定位

**XB-SVCB 是一个桌面级 AI 翻唱工作站**，核心能力是：

- 导入歌曲
- 人声 / 伴奏分离
- 去混响 / 去回声
- So-VITS-SVC / RVC 歌声转换
- 单模型翻唱
- 多模型混合翻唱 / 合唱
- 歌词时间轴分配
- 自动混音 / 人声合并
- 作品库管理
- 在线曲库下载
- ModelScope 模型站上传 / 下载
- 内置轻量多轨音频编辑器
- Windows 图形安装器与运行环境搭建

一句话定位：

> **AI 语音转换平台 + 模型中心 + 混唱工作台 + 音频编辑器 + 创作工作流管理。**

---

## 2. 当前技术栈

### 2.1 桌面壳 / 后端

目录：`app/`

| 层 | 技术 | 说明 |
|---|---|---|
| 桌面壳 | `pywebview` | Python 桌面 WebView，加载前端资源 |
| 后端语言 | Python 3.10+ | 主程序与业务服务 |
| 依赖管理 | `uv` | 见 `app/uv.lock`、`install/install.py` |
| HTTP / API 客户端 | `httpx[http2]` | 在线曲库、ModelScope API |
| 本地桥接 | pywebview JS API | 前端调用 `window.pywebview.api.*` |
| 打包 | PyInstaller | 见 `installer/xb-svcb-app.spec` |
| 音频处理 | ffmpeg / ffprobe | 转码、剪辑、混音、波形、静音检测 |
| AI 分离 | audio-separator / UVR | 独立 `.venv-uvr` |
| AI 推理 | So-VITS-SVC 4.1 | 独立 `.venv-svc` |
| AI 推理 | RVC / rvc-python | 独立 `.venv-rvc` |
| 模型站上传 | modelscope SDK | 独立 `.venv-hub` |

后端主环境依赖：

```toml
httpx[http2]>=0.28.1
pywebview>=6.2.1
```

来源：`app/pyproject.toml`。

### 2.2 前端

目录：`web/`

| 类型 | 技术 |
|---|---|
| 框架 | React 19 + TypeScript |
| 构建 | Vite |
| UI | Ant Design |
| 状态 | Zustand |
| 路由 | React Router |
| 数据请求 / 轮询 | TanStack Query |
| 表单 | React Hook Form + Zod |
| 测试 | Vitest + React Testing Library |
| 图标 | lucide-react 或 Ant Design Icons |

主要脚本：

```json
{
  "dev": "vite",
  "build": "run-p type-check \"build-only {@}\" --",
  "preview": "vite preview",
  "test:unit": "vitest",
  "build-only": "vite build",
  "type-check": "vue-tsc --build"
}
```

来源：`web/package.json`。

### 2.3 安装 / 打包

当前安装器是 **Windows 专用**：

| 文件 | 作用 |
|---|---|
| `installer/build.ps1` | 构建前端、PyInstaller 应用、Inno Setup 安装包 |
| `installer/xb-svcb-app.spec` | PyInstaller 规格 |
| `installer/xb-svcb.iss` | Inno Setup 脚本 |
| `setup_env.bat` | 用户机运行环境搭建入口 |
| `install/install.py` | 安装 AI 环境 / 下载模型 / 克隆引擎 |
| `install_prereqs.bat` | 安装器前置依赖辅助 |
| `run.bat` / `run.ps1` | 源码运行入口 |

---

## 3. 目录结构与职责

```text
VCA-Studio/
├─ app/                       # Python 桌面壳 + 后端业务
│  ├─ api/                    # pywebview 桥接层
│  │  └─ bridge.py
│  ├─ application/            # 应用服务 / 用例编排
│  │  ├─ audio_editor_service.py
│  │  ├─ conversion_service.py
│  │  ├─ model_hub_service.py
│  │  ├─ model_service.py
│  │  ├─ music_service.py
│  │  ├─ system_service.py
│  │  └─ work_service.py
│  ├─ domain/                 # 领域实体、枚举
│  │  ├─ audio_editor.py
│  │  ├─ entities.py
│  │  └─ enums.py
│  ├─ infrastructure/         # 外部工具 / 存储 / 推理引擎适配
│  │  ├─ audio_engine.py
│  │  ├─ engine.py
│  │  ├─ ffmpeg_tool.py
│  │  ├─ rvc_engine.py
│  │  ├─ svc_engine.py
│  │  ├─ uvr_tool.py
│  │  ├─ *_worker.py
│  │  ├─ storage.py
│  │  ├─ paths.py
│  │  └─ window_theme.py
│  ├─ config.py               # 全局配置、路径、环境变量
│  └─ main.py                 # 桌面应用入口
├─ web/                       # React + Vite 前端
│  ├─ src/api/                # 前端 API 封装 / mock / 类型
│  ├─ src/components/         # 公共组件
│  ├─ src/layouts/            # 页面布局
│  ├─ src/router/             # 路由
│  ├─ src/stores/             # Zustand store
│  └─ src/views/              # 页面
├─ install/                   # 用户机环境搭建脚本
├─ installer/                 # Windows 安装包构建
├─ assets/
│  ├─ icon/                   # 图标
│  └─ models/                 # 预置底模 / UVR 模型
├─ README.md
├─ release_notes_v*.md
├─ run.bat
├─ run.ps1
├─ setup_env.bat
└─ install_prereqs.bat
```

---

## 4. 应用启动与桥接架构

### 4.1 主入口

主入口：`app/main.py`

职责：

1. 判断开发 / 生产模式
2. 开发模式加载 Vite dev server
3. 生产模式加载 `web/dist/index.html`
4. 创建 pywebview 窗口
5. 注入 Python API 到 JS
6. 设置 WebView 持久化目录
7. 生产模式清理 WebView2 缓存
8. 启动 pywebview

启动方式：

```bash
uv run python main.py
uv run python main.py --dev
```

### 4.2 前后端桥接

后端桥接：`app/api/bridge.py`

`Api` 的公有方法暴露为：

```text
window.pywebview.api.<method>
```

前端统一 API：`web/src/api/index.ts`

特点：

- 桌面环境走 pywebview API
- 浏览器开发环境走 mock
- 所有能力集中在 `web/src/api/index.ts`
- 类型集中在 `web/src/api/types.ts`

### 4.3 后端组合根

服务装配在 `build_api()`：`app/api/bridge.py`

装配内容：

```python
ffmpeg = FfmpegTool()
uvr = UvrTool()
svc = SvcEngine()
rvc = RvcEngine()
engines = EngineRegistry([svc, rvc])

models_repo = ListRepository(config.MODELS_DB)
works_repo = ListRepository(config.WORKS_DB)
editor_repo = ListRepository(config.EDITOR_PROJECTS_DB)
settings = SettingsStore(config.SETTINGS_DB)

system_service = SystemService(...)
model_service = ModelService(...)
conversion_service = ConversionService(...)
work_service = WorkService(...)
music_service = MusicService(...)
hub_service = ModelHubService(...)
editor_service = AudioEditorService(...)
```

这是复刻项目最关键的后端组合点。

---

## 5. 配置、路径与数据存储

核心文件：`app/config.py`

### 5.1 应用元信息

```python
APP_NAME = "VCA-Studio"
APP_TITLE = "VCA-Studio"
APP_VERSION = "0.1.0"
```

### 5.2 运行基准目录

支持源码运行与 PyInstaller 打包：

- 源码运行：
  - `BASE_DIR = 项目根`
  - `BUNDLE_DIR = app/`
- 打包后：
  - `BASE_DIR = exe 所在目录`
  - `BUNDLE_DIR = PyInstaller _internal`

前端产物路径：

```python
DIST_INDEX = BUNDLE_DIR / "web" / "dist" / "index.html"  # 打包
DIST_INDEX = ROOT_DIR / "web" / "dist" / "index.html"    # 源码
```

### 5.3 AI 环境路径

默认安装目录下：

| 路径 | 作用 |
|---|---|
| `engines/so-vits-svc` | So-VITS-SVC 仓库 |
| `.venv-svc` | SVC 推理环境 |
| `.venv-rvc` | RVC 推理环境 |
| `.venv-uvr` | UVR 分离环境 |
| `.venv-hub` | ModelScope 上传环境 |
| `models/uvr` | UVR 模型 |

### 5.4 可覆盖环境变量

| 环境变量 | 作用 |
|---|---|
| `XB_DEV` | 开发模式 |
| `XB_DEV_URL` | Vite dev server URL |
| `XB_SOVITS_REPO` | So-VITS-SVC 仓库 |
| `XB_SVC_PYTHON` | SVC 推理 Python |
| `XB_RVC_PYTHON` | RVC 推理 Python |
| `XB_UVR_PYTHON` | UVR Python |
| `XB_UVR_MODEL_DIR` | UVR 模型目录 |
| `XB_UVR_SEP_MODEL` | UVR 分离模型 |
| `XB_UVR_DEREVERB_MODEL` | UVR 去混响模型 |
| `XB_HUB_PYTHON` | ModelScope 上传 Python |
| `VCA_DATA_DIR` | 用户数据目录 |
| `XB_SVCB_DATA_DIR` | 旧兼容数据目录变量 |
| `VCA_LEGACY_DATA_DIR` | 兼容旧版本数据目录变量 |
| `XB_HF_MIRROR` | HuggingFace 镜像 |
| `XB_GH_MIRROR` | GitHub 镜像 |

### 5.5 用户数据目录

默认数据目录名：

```python
DATA_DIR_NAME = ".vca_studio"
```

数据目录优先级：

1. 环境变量
2. `data_home.json`
3. 安装目录 / 用户目录中的 `.vca_studio`
4. 默认安装目录下 `.vca_studio`

核心数据文件：

| 路径 | 作用 |
|---|---|
| `.vca_studio/models` | 导入的声音模型 |
| `.vca_studio/works` | 作品与中间产物 |
| `.vca_studio/temp` | 临时文件 |
| `.vca_studio/music` | 在线下载歌曲 |
| `.vca_studio/webview` | WebView localStorage / cookie |
| `.vca_studio/models.json` | 模型记录 |
| `.vca_studio/works.json` | 作品记录 |
| `.vca_studio/settings.json` | 设置 |
| `.vca_studio/editor` | 编辑工程目录 |
| `.vca_studio/editor_projects.json` | 编辑工程记录 |
| `.vca_studio/modelhub` | 模型站上传 / 下载暂存 |

存储实现：`app/infrastructure/storage.py`

- `JsonStore`
- `ListRepository`
- `SettingsStore`

特点：

- JSON 文件持久化
- 线程锁保护
- 写入采用 `.tmp` 后 replace
- 简单、够用、容易迁移

---

## 6. 前端页面与路由

新项目 VCA-Studio 前端建议使用 React 生态，页面路径按 React 约定调整：

| 路由 | 页面 | 功能 |
|---|---|---|
| `/` | `pages/Home.tsx` | 首页 / 最近作品 / 数据目录 |
| `/create` | `pages/Create.tsx` | 新建翻唱 |
| `/models` | `pages/Models.tsx` | 声音模型管理 |
| `/runtime` | `pages/Runtime.tsx` | 运行环境检测 / 路径接入 / 整合包导入 |
| `/works` | `pages/Works.tsx` | 作品库 |

P0 暂不把在线曲库、模型站、完整音频编辑器放进主导航；后续阶段再加：

| 后续路由 | 页面 | 功能 |
|---|---|---|
| `/music` | `pages/Music.tsx` | 在线资源获取 |
| `/model-hub` | `pages/ModelHub.tsx` | ModelScope 模型站 |
| `/editor/projects` | `pages/editor/Projects.tsx` | 编辑工程选择页 |
| `/editor` | `pages/editor/Editor.tsx` | 音频编辑器 |

---

## 7. 核心功能模块

### 7.1 系统状态 / 数据目录迁移

后端文件：

- `app/application/system_service.py`
- `app/api/bridge.py`
- `app/config.py`

能力：

1. 检测 ffmpeg
2. 检测 UVR
3. 检测 So-VITS-SVC
4. 检测 RVC
5. 查看数据目录
6. 统计数据目录占用
7. 选择新数据目录
8. 数据目录迁移
9. 启动后清理旧数据目录

迁移保护：

- 有推理任务运行 / 排队时禁止迁移
- 目标目录不能是当前目录
- 目标目录不能互为父子
- 非空目录必须有数据标记
- 检查磁盘剩余空间
- 检查可写性
- 写入迁移标记
- 重启后自动清理旧目录

### 7.2 模型管理

后端文件：

- `app/application/model_service.py`
- `app/domain/entities.py`
- `app/api/bridge.py`

支持框架：

| 框架 | 文件要求 |
|---|---|
| So-VITS-SVC | 主模型 `.pth` + `config.json`，可选浅扩散 `.pt` + `.yaml` |
| RVC | 主模型 `.pth`，可选 `.index` |
| DDSP-SVC / other | 有标签预留，但当前推理只支持 so-vits-svc / rvc |

功能：

1. 导入模型
2. 删除模型
3. 设置默认模型
4. 模型收藏
5. 模型库概览
6. 模型按框架统计
7. 模型体积统计
8. 模型健康检查
9. RVC `.index` 自动候选修复
10. So-VITS 配置采样率解析
11. 模型元数据标准化

### 7.3 AI 翻唱任务 / 作品库

后端文件：

- `app/application/work_service.py`
- `app/application/conversion_service.py`
- `app/domain/entities.py`

工作流类型：

| workflow | 说明 |
|---|---|
| `auto_mix` | 自动混音合成 |
| `auto_vocal_merge` | 自动人声合并 |
| `manual_vocal_merge` | 手动人声合并 |
| `auto_then_editor` | 自动 + 编辑器二次调整 |
| `full_manual_editor` | 全手动编辑 |

任务队列特点：

- 串行执行，避免单 GPU 并发导致 OOM
- 后台线程执行
- 前端轮询作品进度

### 7.4 单模型翻唱流程

当前项目默认流程：

1. 创建作品记录
2. 加入串行队列
3. 人声 / 伴奏分离
4. 可选去混响
5. 准备推理输入
6. So-VITS-SVC 进行 F0 提取
7. 根据模型框架路由到 SVC / RVC
8. 生成 AI 人声
9. 与伴奏混音
10. 更新作品状态、进度、日志

默认步骤：

```python
[
  人声分离,
  F0 提取,
  模型推理,
  混音合成
]
```

当前“不满意点”：**任务固定从 UVR 人声分离开始**。如果用户已经提前分离好人声 / 伴奏，仍会重新跑一遍分离，浪费时间。

#### 分离阶段实际做了什么

当前分离阶段不只是 UVR 拆轨，还包含几个必要处理：

1. **源音频规范化**  
   先用 ffmpeg 把输入统一转成标准 WAV，修正在线下载素材扩展名错配问题，例如 `.m4a/.flac` 被误存成 `.mp3`。这一步不应跳过。

2. **UVR 人声 / 伴奏分离**  
   输出：
   - `vocals`：人声
   - `instrumental`：伴奏

3. **失败降级**  
   UVR 不可用或失败时，直接把原音频当作人声继续跑，保证链路不中断，但没有伴奏。

4. **可选去混响 / 去回声**  
   如果 `UVR-DeEcho-DeReverb.pth` 可用，会对分离后人声再跑一次去混响，缓解电音 / 机械音。

5. **保存路径**  
   写入：
   - `vocals_path`
   - `instrumental_path`

所以新项目如果支持“跳过分离”，不能简单跳过整个步骤，至少要保留 **音频规范化** 和可选 **去混响**。

#### 建议新增输入模式

不要只做一个“跳过分离”按钮，建议明确区分用户提供了什么：

```text
1. 完整歌曲，自动分离
   输入：完整歌曲
   流程：转 WAV → UVR 分离 → 可选去混响 → 推理 → 混音

2. 已分离人声
   输入：人声文件
   流程：人声转 WAV → 可选去混响 → 推理
   输出：默认仅 AI 干声；没有伴奏，不做完整混音

3. 已分离人声 + 伴奏
   输入：人声文件 + 伴奏文件
   流程：人声 / 伴奏转 WAV → 可选去混响 → 推理 → 与伴奏混音
```

推荐 payload 字段：

```ts
input_mode?: 'song' | 'stems'
vocals_path?: string | null
instrumental_path?: string | null
skip_dereverb?: boolean
```

含义：

| 字段 | 说明 |
|---|---|
| `input_mode: 'song'` | 当前默认模式，完整歌曲自动分离 |
| `input_mode: 'stems'` | 用户已提供分离素材 |
| `vocals_path` | 已分离人声，`stems` 模式必填 |
| `instrumental_path` | 已分离伴奏，可选；存在时最终混音 |
| `skip_dereverb` | 是否跳过去混响；已处理过的人声建议默认跳过 |

#### 后端最小实现建议

在 `ConversionService` 抽一个共用准备函数，避免单模型 / 多模型各复制一遍：

```python
def _prepare_stems(work, work_dir, log_file, params):
    ...
    return vocals, instrumental, duration
```

逻辑：

```text
if input_mode == 'stems':
    vocals = vocals_path
    instrumental = instrumental_path 可选
    vocals = normalize vocals to wav
    instrumental = normalize instrumental to wav if exists
    if not skip_dereverb and uvr_dereverb_ready:
        vocals = dereverb(vocals)
else:
    source = source_path
    source = normalize source to wav
    sep = uvr.separate(source)
    vocals = sep.vocals
    instrumental = sep.instrumental
    if uvr_dereverb_ready:
        vocals = dereverb(vocals)
```

注意：

- 跳过 UVR 分离可以，但不要跳过 WAV 规范化。
- 只有人声、没有伴奏时，最终输出 AI 干声。
- 人声 + 伴奏模式下建议校验二者时长差，差异较大时提示不同步，但不必强行拒绝。
- 已分离人声默认建议 `skip_dereverb = true`，避免重复去混响损伤音质。

#### 前端建议

新建翻唱页增加输入类型：

```text
输入类型：
  ○ 完整歌曲，自动分离
  ○ 已分离人声
  ○ 已分离人声 + 伴奏
```

对应文件选择：

| 模式 | 必填 | 可选 |
|---|---|---|
| 完整歌曲 | 歌曲文件 | 无 |
| 已分离人声 | 人声文件 | 是否去混响 |
| 已分离人声 + 伴奏 | 人声文件、伴奏文件 | 是否去混响 |

文案建议：

- 只有人声：`开始生成干声`
- 人声 + 伴奏：`开始生成翻唱`
- 完整歌曲：`开始生成翻唱`

#### 对多模型流程的影响

多模型同样可行，且更合理：

```text
已有人声 → 每个模型整轨推理 → 按歌词切换 / 合唱 → 与伴奏混音
```

如果只有人声，则输出：

```text
合并后 AI 人声
```

没有伴奏时不做完整混音。

每个作品目录大致为：

```text
.vca_studio/works/<work_id>/
├─ run.log
├─ 分离人声
├─ 伴奏
├─ 去混响人声
├─ infer_input.wav
├─ f0.npy
├─ AI 人声
└─ 最终混音
```

### 7.5 多模型混合翻唱 / 合唱

前端功能：

1. 选择多模型
2. 每个模型独立参数
3. 获取歌词
4. 导入 LRC
5. 歌词时长对齐
6. 时间轴片段调整
7. 逐句指派模型
8. 一句多个模型合唱
9. 拆分 / 合并 / 删除片段
10. 整体偏移

#### LRC / 歌词导入的定位

歌词导入的本质不是“显示歌词”，而是快速生成 **可操作的片段时间轴**。

除了多模型混唱，它还有这些用途：

1. **按歌词切句**  
   把整条人声按 LRC 时间切成句段，服务局部重推理、单句替换、单句导出。

2. **定位问题片段**  
   用户听到某句效果不好，可以点歌词直接跳到对应时间，不用手动拖进度条。

3. **局部重推理**  
   单模型场景也可以选择某句歌词，调整 pitch / f0 / protect 后只重跑该句，再替换回成品。

4. **生成编辑工程**  
   每句歌词可以直接转成一个编辑器 clip，让后期工程天然按句分段。

5. **后续字幕 / MV 扩展**  
   如果将来做歌词字幕、滚动歌词、MV 视频，LRC 是基础数据源。

优先级判断：

```text
P0 单模型翻唱：不需要 LRC
P1 多模型轮唱：需要 LRC 作为时间轴来源
P2 局部重推理 / 编辑器：继续复用 LRC 时间轴
```

核心概念应叫：

```text
Segment Timeline / 片段时间轴
```

LRC 只是生成时间轴的一种方式。后续还可以支持：

- 手动切句
- 静音检测切句
- AI 自动识别歌词 / 时间轴
- 导入工程时间轴

核心数据结构：

```python
mode = "multi"
segments = [
  {
    "start": 0.0,
    "end": 3.2,
    "model_id": "mdl_x",
    "model_ids": ["mdl_x", "mdl_y"]
  }
]
seg_models = {
  model_id: {
    "name": "...",
    "params": {...},
    "framework": "...",
    "main_model_path": "...",
  }
}
```

多模型步骤：

```python
[
  人声分离,
  歌词分割,
  逐段推理,
  人声合并,
  混音合成
]
```

合成策略：

- 每个模型在完整人声上整轨推理
- 不逐句碎片推理，避免电流声 / 咔哒声
- 同一模型连续片段合并
- 换人处交叉淡化
- 合唱句多路人声按 `1/√N` 等响度叠加
- 经 `alimiter` 软限幅防破音

### 7.6 推理引擎抽象

文件：

- `app/infrastructure/engine.py`
- `app/infrastructure/svc_engine.py`
- `app/infrastructure/rvc_engine.py`

统一协议：

```python
framework: str
available: bool
infer(model, vocals, out_path, params, duration, log_file)
```

`EngineRegistry` 按 `framework` 路由：

- `so-vits-svc` → `SvcEngine`
- `rvc` → `RvcEngine`
- 未知回退默认框架

### 7.7 UVR 人声分离

文件：`app/infrastructure/uvr_tool.py`

能力：

- 调用 `.venv-uvr`
- 执行 `uvr_worker.py`
- 使用 `audio-separator`
- 分离人声 / 伴奏
- 支持指定模型
- 支持设备 auto / cuda / cpu
- 输出 `uvr_result.json`
- 失败自动降级为原音频作为人声

默认模型：

- `5_HP-Karaoke-UVR.pth`
- `UVR-DeEcho-DeReverb.pth`

### 7.8 ffmpeg 音频处理

文件：

- `app/infrastructure/ffmpeg_tool.py`
- `app/infrastructure/audio_engine.py`

`FfmpegTool` 能力：

1. 检测 ffmpeg / ffprobe
2. 获取版本
3. 探测音频时长
4. 静音检测
5. 转码
6. 精确切片
7. 拼接
8. 混音
9. 格式处理

`FFmpegEngine` 是音频编辑器专用封装，支持：

- 多轨
- 片段 offset
- 片段 start / end
- 音量
- fade in / fade out
- 左 / 右 / 双声道
- delay
- amix
- alimiter
- wav / mp3 / flac 输出

### 7.9 在线音乐资源

文件：

- `app/application/music_service.py`
- `web/src/views/music/music.vue`
- `web/src/views/create/create.vue`

外部服务：妖狐音乐 API

```python
MUSIC_API_BASE = "https://api.yaohud.cn/api/music"
```

支持曲库：

| source | 名称 |
|---|---|
| `wy` | 网易云音乐 |
| `qq` | QQ音乐 |

功能：

1. 用户填写 API Key
2. 曲库选择
3. QQ 音乐 Cookie
4. 搜索歌曲
5. 分页加载
6. 获取单曲信息
7. 下载歌曲
8. 获取歌词
9. 解析 LRC
10. 下载前检测真实音频格式
11. 避免 VIP / 无版权 / HTML 错误体误下载
12. 下载歌曲保存到 `.vca_studio/music`
13. 翻唱页可直接选用下载素材

技术点：

- 独立 asyncio 事件循环线程
- QPS 限流
- httpx 异步请求
- 文件头魔数识别真实音频格式
- LRC 解析

### 7.10 ModelScope 模型站

文件：

- `app/application/model_hub_service.py`
- `app/infrastructure/hub_worker.py`
- `web/src/views/models/models.vue`
- `web/src/stores/transfers.ts`
- `web/src/components/layout/AppHeader.vue`

核心方案：

1. 用户填写自己的 ModelScope token
2. token 保存在本地 `settings.json`
3. 上传发布到用户自己的 namespace
4. 仓库名统一前缀 `vca-studio-`
5. 写入清单 `vca-studio-model.json`
6. 清单含 magic / schema / 文件角色 / framework
7. 搜索时按 marker 全站搜索
8. 只保留前缀 + 清单校验通过的结果
9. 下载后复用 `ModelService.import_model`
10. 上传需要 `.venv-hub`
11. 搜索 / 下载 / token 校验只用 httpx

后台传输支持：

- 上传 / 下载挂后台
- 顶栏传输面板
- 进度轮询
- 完成 / 失败任务清理

进度数据：

```python
{
  "phase": "...",
  "pct": 0-100,
  "msg": "...",
  "done": bytes,
  "total": bytes
}
```

### 7.11 音频编辑器 Audio Editor Lite

文件：

- 后端：`app/application/audio_editor_service.py`
- 领域：`app/domain/audio_editor.py`
- 渲染：`app/infrastructure/audio_engine.py`
- 前端工程页：`web/src/views/editor/projects.vue`
- 前端编辑页：`web/src/views/editor/editor.vue`

数据模型：

`EditorClip`：

```python
id
start
end
offset
volume
mute
file
effects
name
locked
fade_in
fade_out
channel  # stereo / left / right
metadata
```

`EditorTrack`：

```python
id
name
type
clips
locked
mute
volume
```

`EditorProject`：

```python
id
title
tracks
duration
sample_rate
waveform_cache
metadata
created_at
updated_at
```

功能：

1. 工程列表
2. 从本地音频创建工程
3. 从作品创建工程
4. 删除工程
5. 放弃工程
6. 多轨时间轴
7. 新增 / 删除音轨
8. 导入音频到指定轨道
9. 拖动片段
10. 拉伸边界
11. 播放头剪切
12. 静音切句
13. 歌词切分
14. 片段人声分离
15. 片段局部重推理
16. 片段声道分配：双声道 / 左 / 右
17. 音量、静音、锁定
18. 淡入 / 淡出 / 交叉淡化
19. 真实波形缓存
20. 混音预览
21. 导出 WAV / MP3 / FLAC
22. undo / redo，历史上限 60

关键常量：

```python
_HISTORY_LIMIT = 60
_MIN_RERUN_DURATION = 1.0
_RENDER_VERSION = "channel-route-v5-flac-preview"
```

---

## 8. 安装器 / 环境搭建

### 8.1 Windows 安装器能力

文件：`installer/xb-svcb.iss`

安装器做的事：

1. 安装应用本体
2. 复制 `install/`
3. 复制 `setup_env.bat`
4. 复制 `install_prereqs.bat`
5. 复制图标
6. 复制 `assets/models`
7. 创建开始菜单快捷方式
8. 创建桌面快捷方式
9. 可选安装后启动
10. 可选搭建 / 修复运行环境
11. 前置环境检查
12. 自动检测 GPU 栈
13. 检测 / 安装 Python、Git、ffmpeg、uv、CUDA、C++ Build Tools
14. 选择数据目录
15. 写入 `data_home.json`
16. 环境搭建进度显示
17. 安装日志

卸载清理：

- `.venv-uvr`
- `.venv-svc`
- `.venv-rvc`
- `.venv-hub`
- `engines`
- `models`

用户数据 `.vca_studio` 保留。

### 8.2 install.py 环境步骤

文件：`install/install.py`

会创建：

| 步骤 | 产物 |
|---|---|
| app | `app/.venv` |
| web | `web/dist` |
| uvr | `.venv-uvr` |
| svc | `engines/so-vits-svc` + `.venv-svc` |
| rvc | `.venv-rvc` |
| hub | `.venv-hub` |
| models | `models/uvr`、`engines/so-vits-svc/pretrain` |

GPU 栈：

| 返回 | 含义 |
|---|---|
| `cpu` | CPU |
| `cu121` | NVIDIA 40 系及以下 |
| `cu128` | NVIDIA 50 系 / Blackwell |

50 系特别处理：

- CUDA 12.8
- torch 2.7.1
- Python 3.10
- torchaudio I/O 走 soundfile
- fairseq 重装并补丁

### 8.3 新项目运行环境管理设计

当前项目的问题是：安装器同时承担“安装软件本体”和“搭建 AI 运行环境”。这让 SVC / RVC / UVR 的来源、版本和安装路径都偏固定；用户即使已有可用整合包，也容易被迫重新下载或重建环境。

新项目建议拆成两层：

```text
软件安装器：
  只安装应用壳、前端、后端、图标、快捷方式

运行环境管理：
  进入软件后检测依赖，支持手动选择路径、导入整合包，失败时再在线安装
```

#### 安装器职责

安装包只做：

- 安装软件本体
- 创建快捷方式
- 复制前端与后端资源
- 复制图标和说明文档

安装包不强制做：

- 不强制创建 `.venv-svc`
- 不强制创建 `.venv-rvc`
- 不强制下载 so-vits-svc
- 不强制下载 UVR 模型
- 不强制安装 CUDA / torch

这些交给软件内的 **运行环境管理** 页面处理。

#### 运行环境管理模块

建议新增模块：

```text
Runtime Manager / 运行环境管理
```

页面展示每个组件的状态：

| 组件 | 状态 | 操作 |
|---|---|---|
| ffmpeg | 已就绪 / 缺失 | 选择路径 / 在线安装 |
| UVR | 已就绪 / 缺模型 / 缺环境 | 选择路径 / 导入整合包 / 下载 |
| SVC | 已就绪 / 缺 repo / 缺 python / 版本不匹配 | 选择路径 / 导入整合包 / 在线安装 |
| RVC | 已就绪 / 缺 python / 缺底模 | 选择路径 / 导入整合包 / 在线安装 |
| ModelScope 上传 | 已就绪 / 缺 SDK | 选择路径 / 安装 / 跳过 |

统一状态模型建议：

```ts
interface RuntimeComponentStatus {
  key: 'ffmpeg' | 'uvr' | 'svc' | 'rvc' | 'modelhub'
  name: string
  status: 'ready' | 'missing' | 'partial' | 'error'
  message: string
  paths: Record<string, string>
  checks: {
    key: string
    label: string
    ok: boolean
    message: string
  }[]
  actions: ('choose_path' | 'import_bundle' | 'online_install' | 'repair')[]
}
```

#### 首版接入策略

采用“两者都支持，但首版先做手动路径接入”的策略：

```text
首版：用户分别选择路径，程序检测并保存
第二阶段：用户选择整合包目录，程序自动扫描
在线安装：作为检测失败后的兜底
```

首版优先支持用户手动选择：

- `ffmpeg` 路径
- `ffprobe` 路径
- SVC Python
- so-vits-svc 仓库目录
- RVC Python
- UVR Python
- UVR 模型目录
- ModelScope 上传 Python

优点：

- 最稳
- 好排错
- 不依赖整合包目录结构
- 适合优先跑通 RTX 2060 Super 开发环境

#### 整合包导入策略

第二阶段支持选择整合包目录，例如：

```text
选择 SVC 整合包目录
选择 RVC 整合包目录
选择 UVR 整合包目录
```

程序不要相信目录名，而是扫描并检测：

```text
选择目录
→ 扫描候选 python / repo / models
→ 跑检测
→ 展示检测结果
→ 用户确认保存
```

检测不通过时给明确原因：

```text
❌ 未找到 Python
❌ 找到 Python，但缺 torch
❌ 找到 so-vits-svc，但缺 inference/infer_tool.py
❌ torch 可用，但 CUDA 不可用，当前将使用 CPU
```

#### 组件检测规则

##### ffmpeg

检测：

- `ffmpeg` 是否存在
- `ffprobe` 是否存在
- 能否返回版本

优先级：

```text
用户配置路径 > PATH > 缺失
```

##### SVC

检测：

- SVC Python 是否存在
- so-vits-svc repo 是否存在
- `inference/infer_tool.py` 是否存在
- `python -c "import torch"`
- `python -c "import librosa"`
- `python -c "import fairseq"`
- worker 可启动

通过后保存：

```json
{
  "svc_python": "...",
  "sovits_repo": "..."
}
```

当前项目已有环境变量基础：

```text
XB_SVC_PYTHON
XB_SOVITS_REPO
```

新项目建议把它们升级为 UI 可配置项。

##### RVC

检测：

- RVC Python 是否存在
- `python -c "import torch"`
- `python -c "import rvc_python"` 或实际使用模块
- `rvc_worker.py --check` 可启动
- 可选检测 hubert / rmvpe 底模

通过后保存：

```json
{
  "rvc_python": "..."
}
```

当前项目已有环境变量基础：

```text
XB_RVC_PYTHON
```

##### UVR

检测：

- UVR Python 是否存在
- `python -c "import audio_separator"`
- UVR 模型目录是否存在
- `5_HP-Karaoke-UVR.pth` 是否存在
- `UVR-DeEcho-DeReverb.pth` 是否存在

通过后保存：

```json
{
  "uvr_python": "...",
  "uvr_model_dir": "..."
}
```

##### ModelScope 上传组件

检测：

- Hub Python 是否存在
- `python -c "import modelscope"`
- `hub_worker.py --check` 可启动

注意：搜索 / 下载不依赖该组件，只有上传需要。缺失时不应影响主功能。

#### 配置优先级

当前项目主要靠环境变量覆盖。新项目建议同时支持 UI 配置与环境变量：

```text
环境变量 > 用户配置 settings.json > 自动检测默认路径 > PATH
```

好处：

- 高级用户仍可用环境变量覆盖
- 普通用户可以在软件内点选路径
- 离线整合包可以直接接入

#### 在线安装作为兜底

只有检测失败时，才展示：

```text
在线安装 / 修复
```

并明确说明将执行什么：

```text
将下载 so-vits-svc 4.1
将创建 .venv-svc
将安装 torch cu121
预计占用 X GB
```

用户个人开发 PC 是 **RTX 2060 Super**，因此开发优先级是：

```text
先跑通 Windows + RTX 2060 Super + cu121/cu118
再处理 RTX 50 系 cu128、Mac CPU/MPS、其它平台
```

RTX 2060 Super 属于非 50 系 NVIDIA 显卡，不需要优先处理 Blackwell / cu128。

#### 同类依赖问题

除 SVC / RVC 外，类似问题还有：

| 组件 | 当前问题 | 新方案 |
|---|---|---|
| ffmpeg | 依赖 PATH | 支持选择路径 |
| UVR 模型 | 固定模型目录 | 支持导入模型目录 |
| UVR 环境 | 固定 `.venv-uvr` | 支持选择 Python |
| SVC repo | 固定下载源 | 支持选择已有 repo |
| SVC Python | 固定 `.venv-svc` | 支持选择已有 Python |
| RVC Python | 固定 `.venv-rvc` | 支持选择已有 Python |
| 底模 pretrain | 固定复制 / 下载 | 支持导入目录 |
| ModelScope 上传环境 | 固定 `.venv-hub` | 可选安装 |
| CUDA / torch | 安装器里决定 | 软件内检测并推荐 |

---

## 9. 当前平台支持现状

### 9.1 明确支持

| 平台 | 状态 |
|---|---|
| Windows | 完整支持 |
| macOS | 代码部分具备跨平台潜力，但未形成客户端 |
| Linux | 部分基础代码兼容，但未打包发行 |

当前 README 徽章显示平台是 Windows。安装器、脚本、依赖检测目前明显以 Windows 为主。

### 9.2 已有跨平台基础

这些代码已经考虑了非 Windows：

1. venv python 路径兼容 Windows / Unix
2. 子进程隐藏窗口仅 Windows 生效
3. 打开路径支持 Windows / macOS / Linux
4. PyInstaller spec 结构理论上可迁移 macOS
5. pywebview 本身支持 macOS WebKit

### 9.3 Windows 强绑定点

| 文件 / 点 | Windows 绑定 |
|---|---|
| `installer/xb-svcb.iss` | Inno Setup，仅 Windows |
| `installer/build.ps1` | PowerShell + ISCC |
| `setup_env.bat` | batch |
| `install_prereqs.bat` | batch / winget |
| `run.bat` | batch |
| `app/config.py` 部分默认路径 | Windows conda 路径候选 |
| `window_theme.py` | 大概率是 Windows 标题栏主题 |
| pywebview 后端 | 当前 spec 强收集 winforms / edgechromium |
| 安装器 GPU / CUDA 检测 | nvidia-smi / CUDA Windows 逻辑 |
| C++ Build Tools | Windows 专用 |
| ffmpeg 安装 | 当前依赖 winget / Windows PATH |

Mac 版需要替换或分叉这些部分。

---

## 10. 新项目功能对齐清单

### 10.1 基础桌面应用

- [x] React 前端能在浏览器开发模式运行
- [x] pywebview 桌面窗口能加载前端
- [x] 生产模式加载 `web/dist/index.html`
- [x] 前端可调用后端 JS API
- [x] 浏览器开发环境有 mock fallback
- [x] localStorage / cookie 可持久化
- [ ] 数据目录可自定义
- [ ] 数据目录可迁移
- [x] Windows / Mac 均可打开文件和目录
- [x] 应用版本、标题、图标可配置

### 10.2 模型管理

- [x] 导入 So-VITS-SVC 模型
- [x] 导入 So-VITS-SVC 配置
- [x] 可选导入浅扩散模型
- [x] 可选导入浅扩散配置
- [x] 导入 RVC 模型
- [x] 可选导入 RVC `.index`
- [x] 删除模型同步删除本地文件夹
- [x] 设置默认模型
- [ ] 收藏模型
- [ ] 模型按框架展示 / 筛选
- [ ] 模型库统计数量和体积
- [x] 模型健康检查
- [ ] RVC index 自动候选修复
- [ ] So-VITS 配置采样率识别

### 10.3 单模型翻唱

- [x] 选择源音频
- [x] 选择模型
- [x] 设置变调
- [x] 设置 F0 方法
- [x] 设置推理设备 auto / cuda / cpu
- [ ] 设置 So-VITS 扩散比例
- [x] 设置 RVC index rate
- [x] 设置 RVC rms mix
- [x] 设置 RVC protect
- [x] 设置 RVC filter radius
- [ ] 设置 RVC v1 / v2
- [x] 创建任务
- [ ] 串行队列执行
- [ ] 人声分离
- [ ] 去混响
- [ ] F0 提取
- [ ] 模型推理
- [ ] 混音
- [ ] 作品状态轮询
- [x] 失败写日志
- [x] 作品可重试

### 10.4 多模型混合翻唱

- [ ] 选择多个模型
- [ ] 每个模型独立参数
- [ ] 导入本地 LRC
- [ ] LRC 生成片段时间轴
- [ ] 歌词 / 音频整体偏移校正
- [ ] 音频时长校验
- [ ] 歌词 / 片段时间轴显示
- [ ] 逐句分配单个模型
- [ ] 批量模型分配
- [ ] 未指派区间填充静音 / 原始人声占位
- [ ] 每个模型整轨推理
- [ ] 按分配片段裁切
- [ ] 同源连续片段合并
- [ ] 换人处交叉淡化
- [ ] 自动人声合并
- [ ] 输出混合翻唱成品

后置增强：

- [ ] 获取在线 LRC 歌词
- [ ] 单句多模型合唱
- [ ] 合唱等响度叠加
- [ ] 软限幅防爆音
- [ ] 片段拖动边界
- [ ] 吸附歌词时间
- [ ] 时间轴缩放
- [ ] 片段拆分
- [ ] 片段合并
- [ ] 片段删除
- [ ] 手动人声合并

### 10.5 高级工作流

- [ ] 自动混音合成
- [ ] 自动人声合并
- [ ] 手动人声合并
- [ ] 自动 + 编辑器二次调整
- [ ] 全手动编辑
- [ ] 单模型禁用人声合并类工作流
- [ ] 多模型可进入编辑工程

### 10.6 作品库

- [x] 作品列表
- [x] 最近作品
- [x] 作品状态展示
- [x] 进度条
- [x] 步骤状态
- [ ] 成品试听
- [ ] 伴奏试听
- [ ] 干声试听
- [x] 导出成品
- [x] 重命名作品
- [x] 删除作品
- [x] 删除作品时同步删除真实文件
- [x] 打开日志
- [x] 打开路径
- [x] 推理历史

### 10.7 在线音乐资源

- [ ] 配置妖狐 API Key
- [ ] 支持网易云
- [ ] 支持 QQ 音乐
- [ ] QQ Cookie 配置
- [ ] 搜索歌曲
- [ ] 分页加载更多
- [ ] 试听 / 校验歌曲
- [ ] 下载歌曲
- [ ] 下载前校验音频格式
- [ ] 识别真实扩展名
- [ ] VIP / 无版权 / 失效资源拒绝下载
- [ ] 下载素材列表
- [ ] 删除素材
- [ ] 下载素材一键进入翻唱
- [ ] 获取歌词

### 10.8 ModelScope 模型站

- [ ] 配置 ModelScope token
- [ ] 校验 token
- [ ] 按关键词搜索模型
- [ ] 按框架筛选
- [ ] 分页加载
- [ ] 读取远程清单
- [ ] 清单 magic / schema 校验
- [ ] 下载模型
- [ ] 下载后导入本地模型
- [ ] 上传本地模型
- [ ] 自动生成 manifest
- [ ] 仓库名前缀规范
- [ ] 后台上传 / 下载
- [ ] 顶栏传输面板
- [ ] 进度条
- [ ] 清理完成 / 失败任务

### 10.9 音频编辑器

- [ ] 工程列表
- [ ] 创建空 / 手动工程
- [ ] 从音频创建工程
- [ ] 从作品创建工程
- [ ] 删除工程
- [ ] 放弃工程
- [ ] 多轨时间轴
- [ ] 新增音轨
- [ ] 删除音轨
- [ ] 导入音频到指定轨道
- [ ] 片段拖动
- [ ] 片段边界拉伸
- [ ] 播放头剪切
- [ ] 切口交叉淡化
- [ ] 片段静音
- [ ] 片段锁定
- [ ] 轨道静音
- [ ] 轨道锁定
- [ ] 音量调整
- [ ] 淡入淡出
- [ ] 片段声道：stereo / left / right
- [ ] 混音预览
- [ ] 真实波形
- [ ] 波形缓存
- [ ] 静音检测切句
- [ ] 歌词切分
- [ ] 片段人声分离
- [ ] 局部重推理
- [ ] 1 秒最短片段保护
- [ ] undo / redo
- [ ] 导出 WAV
- [ ] 导出 MP3
- [ ] 导出 FLAC

### 10.10 安装 / 环境

- [ ] 安装主程序环境
- [x] 构建前端
- [ ] 安装 UVR 环境
- [ ] 安装 SVC 环境
- [ ] 安装 RVC 环境
- [ ] 安装 ModelScope 上传环境
- [ ] 下载 / 复制底模
- [ ] 下载 / 复制 UVR 模型
- [x] 检查 ffmpeg
- [ ] 检查 Python
- [ ] 检查 Git
- [ ] 检查 uv
- [ ] 检查 GPU
- [ ] CPU / CUDA 自动选择
- [ ] 50 系 Blackwell 特殊处理
- [ ] 安装日志
- [ ] 幂等重跑
- [ ] 单步重跑
- [ ] 安装失败给出可读错误

---

## 11. Mac 客户端新增建议

### 11.1 最小可行路线

建议不要重写 Electron / Tauri。新项目桌面层仍建议用 pywebview，但前端从当前参考项目的 Vue 生态换成 React 生态：

> **保留 Python + pywebview 架构，前端使用 React + Vite + TypeScript，并新增 macOS 打包与安装脚本。**

原因：

- 前端完全复用
- 后端大部分复用
- pywebview 支持 macOS
- AI 子环境仍然用 venv 隔离
- 不需要引入 Electron 体积与 Node 桌面壳复杂度

### 11.2 Mac 需要新增的内容

建议新增：

```text
installer/
├─ build_macos.sh
├─ vca-studio-mac.spec
└─ mac/
   ├─ entitlements.plist
   ├─ Info.plist 可选模板
   └─ postinstall.sh 可选
install/
├─ install_macos.sh
└─ prereqs_macos.sh
run.command
```

或者更简单：

```text
scripts/
├─ build-mac.sh
├─ setup-env-mac.sh
└─ run-mac.sh
```

Mac 初版可以是：

1. `.app` 包
2. 首次启动提示运行环境未就绪
3. 用户点“搭建运行环境”
4. 调用 shell 脚本安装 venv / 模型
5. 发布 `.dmg` 或 zip

### 11.3 Mac 打包注意点

#### pywebview

Mac 不需要 Windows Edge WebView2，使用系统 WebKit。PyInstaller spec 要移除 Windows hiddenimports：

```python
"webview.platforms.winforms",
"webview.platforms.edgechromium",
"clr",
```

Mac spec 应该避免这些 Windows 专用项。

#### PyInstaller app bundle

Mac 目标产物：

```text
dist/VCA-Studio.app
```

而不是：

```text
dist/VCA-Studio/VCA-Studio.exe
```

#### ffmpeg

Mac 可选方案：

1. 要求用户安装 Homebrew + `brew install ffmpeg`
2. 安装器自动下载静态 ffmpeg
3. app 内置 ffmpeg 二进制

最省事：初版用 Homebrew 检测 / 引导。面向普通用户时，再考虑内置 ffmpeg。

#### Python / uv

Mac 可以用：

```bash
python3
uv
```

建议：

- 检查 `python3`
- 检查版本
- 缺失时提示安装 Python.org 或 Homebrew
- 检查 `uv`
- 缺失时用 `python3 -m pip install uv`

#### GPU

Mac 没有 NVIDIA CUDA。

Mac 版初期建议：

- SVC / RVC 全部默认 CPU
- 不做 CUDA 分支
- Apple Silicon MPS 暂不承诺，除非实测依赖支持
- UI 上显示：`CPU 模式 / macOS 暂不支持 CUDA`

### 11.4 Mac 数据目录建议

当前默认建议是安装目录下 `.vca_studio`。Mac 上 `.app` 内部不适合写数据。

建议 Mac 默认改为：

```text
~/Library/Application Support/VCA-Studio/.vca_studio
```

同时继续允许 `VCA_DATA_DIR` 覆盖。

### 11.5 Mac 环境目录建议

AI 环境不要放进 `.app` 内部。建议放：

```text
~/Library/Application Support/VCA-Studio/runtime/
├─ .venv-uvr
├─ .venv-svc
├─ .venv-rvc
├─ .venv-hub
├─ engines/
└─ models/
```

---

## 12. P0 技术实现建议

P0 目标不是完整复刻当前项目，而是先跑通 **AI 翻唱核心闭环**：

```text
导入模型
→ 检测运行环境
→ 输入完整歌曲 / 已分离人声 / 人声+伴奏
→ SVC/RVC 推理
→ 有伴奏则混音
→ 导出结果
→ 日志可查、失败可重试
```

围绕这个目标，当前项目里有几处不建议原样照搬。

### 12.1 保留的技术栈

这些技术当前够用，P0 不建议替换：

| 技术 | 建议 | 原因 |
|---|---|---|
| React 19 | 保留/采用 | 用户更熟悉 React 生态，前端后续升级空间更大 |
| Vite | 保留/采用 | 桌面 WebView 前端构建够快够简单 |
| TypeScript | 保留/采用 | pywebview bridge 类型约束更稳 |
| Ant Design | 采用 | 管理台 / 表单 / 表格 / 步骤条场景契合 P0 |
| Zustand | 采用 | 少样板，适合本地桌面状态 |
| TanStack Query | 采用 | 适合状态轮询、任务进度、运行环境检测 |
| React Hook Form + Zod | 采用 | 适合模型导入、运行环境路径配置、推理参数表单 |
| Vitest + React Testing Library | 采用 | 与 Vite 组合轻量 |
| pywebview | 保留 | 本地 Python AI 调用方便 |
| Python 后端 | 保留 | 可直接调用推理环境和 ffmpeg |
| JSON 存储 | P0 保留 | 简单稳定，够用 |
| ffmpeg | 保留 | 音频处理必需 |
| PyInstaller | 保留 | 桌面打包够用 |

P0 暂不建议引入：

| 技术 | 原因 |
|---|---|
| Electron | 增加体积和双运行时复杂度 |
| Tauri | Python AI 交互反而更绕 |
| SQLite | P0 JSON 够用，先别加 |
| Celery / Redis | 单机桌面没必要 |
| FastAPI 本地服务 | pywebview bridge 够用 |
| 插件系统 | 过早抽象 |

### 12.2 不建议照搬的实现

#### 1. 不照搬“安装器一把梭搭环境”

当前安装器同时安装软件和 AI runtime，失败原因复杂。P0 应改为：

```text
安装器只装软件
RuntimeManager 在软件内检测 / 导入 / 修复环境
```

这是新项目最关键的技术调整。

#### 2. 不照搬“分离固定第一步”

当前流程固定：

```text
source_path → normalize → UVR separate → dereverb → infer
```

P0 应改为输入模式：

```ts
type InputMode = 'song' | 'vocals' | 'stems'
```

| 模式 | 输入 | 输出 |
|---|---|---|
| `song` | 完整歌曲 | vocals + instrumental |
| `vocals` | 人声 | vocals |
| `stems` | 人声 + 伴奏 | vocals + instrumental |

所有模式都必须走：

```text
音频规范化 → 44100Hz WAV
```

可以跳过 UVR，但不能跳过规范化。

#### 3. 不照搬“推理不可用生成占位音频”

当前项目为了 demo 友好，在 SVC/RVC 不可用时会生成占位音频。P0 产品模式不建议这样做。

建议规则：

| 场景 | 行为 |
|---|---|
| ffmpeg 缺失 | 阻止任务 |
| SVC/RVC 缺失 | 阻止任务 |
| UVR 缺失且 `input_mode=song` | 阻止任务，提示改用已分离人声 |
| UVR 缺失且 `input_mode=vocals/stems` | 允许继续 |
| 没伴奏 | 明确输出 AI 干声 |
| 推理失败 | 任务失败，不生成假结果 |

模拟 / 占位音频只应在开发模式启用，例如：

```text
XB_DEV=1 时允许 simulated
生产模式真实失败就失败
```

#### 4. 不照搬巨大 `ConversionService`

当前 `ConversionService` 同时负责队列、分离、推理、混音、多模型合并、编辑器素材生成，P0 不稳定。

建议拆成少量真实边界，不做过度抽象：

```text
ConversionService
  ├─ StemPreparer
  ├─ InferenceRunner
  └─ MixService
```

职责：

| 模块 | 职责 |
|---|---|
| `StemPreparer` | 处理 `song/vocals/stems`，统一转 WAV，可选 UVR / 去混响 |
| `InferenceRunner` | 按模型 framework 调 SVC/RVC，真实失败就失败 |
| `MixService` | 有伴奏则混音，无伴奏输出干声，负责导出格式 |
| `ConversionService` | 只做任务编排、进度、日志 |

这样“已分离人声跳过 UVR”会自然落在 `StemPreparer`，不会污染推理逻辑。

#### 5. 不照搬完整音频编辑器作为 P0

当前音频编辑器价值高，但工程量大，会稀释核心闭环。P0 只需要：

```text
输入音频
生成结果
试听
导出
查看日志
```

多轨编辑、波形、局部重推理、声道、undo/redo 后置。

#### 6. 不把在线曲库 / ModelScope 当 P0

在线曲库和模型站是生态功能，不是第一阶段核心闭环。P0 只保留本地模型导入和本地音频输入即可。

### 12.3 P0 推荐模块边界

```text
RuntimeManager
  - 检测 ffmpeg / SVC / RVC / UVR
  - 保存用户路径
  - 返回状态

ModelService
  - 导入 SVC/RVC 模型
  - 检查模型文件

StemPreparer
  - song / vocals / stems 三种输入
  - 统一转 WAV
  - 可选 UVR
  - 可选去混响

InferenceRunner
  - 根据 framework 调 SVC/RVC
  - 真实失败就失败，不生成假音频

MixService
  - 有伴奏则混音
  - 无伴奏则输出干声
  - 导出 WAV / MP3

WorkService
  - 创建任务
  - 串行队列
  - 状态
  - 日志
```

### 12.4 P0 模块契约

这一层只细化到“输入 / 输出 / API / 不做什么”，不进入函数级设计。

#### RuntimeManager

负责：

```text
检测运行环境
保存用户选择路径
给前端返回可读状态
```

输入：

```text
用户选择的 ffmpeg / SVC / RVC / UVR 路径
```

输出：

```ts
RuntimeStatus {
  ffmpeg: ComponentStatus
  svc: ComponentStatus
  rvc: ComponentStatus
  uvr: ComponentStatus
}
```

P0 API：

```text
get_runtime_status()
set_runtime_path(key, path)
check_runtime_component(key)
```

P0 不做：

```text
不自动下载
不自动修复
不管理多版本 runtime
```

#### ModelService

负责：

```text
导入模型
保存模型记录
检测模型文件是否完整
```

输入：

```text
framework: svc | rvc
模型文件路径
配置文件路径
index 文件路径
模型名称
```

输出：

```ts
Model {
  id: string
  name: string
  framework: 'svc' | 'rvc'
  files: Record<string, string>
  status: 'ready' | 'missing' | 'error'
  created_at: string
}
```

P0 API：

```text
list_models()
import_model(payload)
check_model(id)
delete_model(id)
```

P0 不做：

```text
不做模型站
不做评分标签
不做自动识别所有模型格式
```

#### StemPreparer

负责：

```text
把用户输入变成标准 vocals / instrumental
```

输入模式：

```ts
input_mode: 'song' | 'vocals' | 'stems'
```

输出：

```ts
PreparedStems {
  vocals_path: string
  instrumental_path?: string
  duration: number
  sample_rate: number
}
```

内部步骤：

```text
复制输入文件到 work_dir/input
统一转 44100Hz wav
song 模式调用 UVR
vocals/stems 模式跳过 UVR
可选去混响
```

P0 不做：

```text
不做推理
不做混音
不做多模型切片
```

#### InferenceRunner

负责：

```text
根据模型 framework 调用 SVC / RVC 引擎
```

输入：

```ts
model_id: string
vocals_path: string
params: InferenceParams
```

输出：

```ts
InferenceResult {
  converted_vocal_path: string
  engine: 'svc' | 'rvc'
  device: 'cuda' | 'cpu' | 'unknown'
}
```

P0 行为：

```text
SVC/RVC 环境不可用 → 失败
模型文件缺失 → 失败
子进程失败 → 失败并写日志
```

P0 不做：

```text
不生成占位音频
不自动切多模型
不吞异常假成功
```

#### MixService

负责：

```text
把 AI 人声和伴奏合成最终结果
```

输入：

```text
converted_vocal_path
instrumental_path?
output_format
```

输出：

```ts
MixResult {
  output_path: string
  mode: 'mixed' | 'vocal_only'
  format: 'wav' | 'mp3'
  duration: number
  size: string
}
```

P0 行为：

```text
有伴奏 → 混音
无伴奏 → 输出 AI 干声
默认 WAV
MP3 可选
```

P0 不做：

```text
不做多轨编辑
不做响度母带处理
不做 FLAC
```

#### WorkService

负责：

```text
创建任务
串行队列
状态更新
日志记录
失败重试
```

状态：

```text
queue
running
done
failed
cancelled
```

P0 API：

```text
create_work(payload)
get_work(id)
list_works()
retry_work(id)
delete_work(id)
export_work(id)
```

工作目录：

```text
.vca_studio/works/<work_id>/
├─ input/
├─ prepared/
├─ output/
├─ run.log
└─ work.json
```

#### P0 主流程

```text
Create 页面提交
→ WorkService.create_work()
→ 复制输入到 work_dir/input
→ StemPreparer.prepare()
→ InferenceRunner.run()
→ MixService.render()
→ WorkService 标记 done / failed
→ 前端轮询 get_work()
```

### 12.6 引擎接口增强

当前已有 `EngineRegistry` 是对的，但 SVC/RVC 引擎接口还应补检测能力。

建议接口：

```python
class VoiceEngine:
    framework: str

    def check(self) -> EngineCheckResult:
        ...

    def infer(...) -> Path:
        ...
```

`check()` 返回：

```ts
{
  ok: boolean
  device: 'cuda' | 'cpu' | 'mps' | 'unknown'
  version: string
  checks: [
    { key: string, ok: boolean, message: string }
  ]
}
```

运行环境页和实际推理共用同一套检测逻辑，避免“页面显示可用，推理时才炸”。

### 12.7 任务状态与日志

当前文本 `run.log` 可以保留，但建议增加轻量结构化步骤状态：

```json
{
  "steps": [
    {
      "key": "prepare_stems",
      "status": "done",
      "started_at": "...",
      "ended_at": "...",
      "message": "...",
      "outputs": {
        "vocals": "...",
        "instrumental": "..."
      }
    }
  ]
}
```

P0 不需要数据库，仍写 JSON 即可。

任务状态建议预留：

```text
queue | running | done | failed | cancelled
```

第一版可以不强杀子进程，但数据结构要有 `cancelled`，后续补取消不会痛。

### 12.8 路径安全策略

用户选择的输入音频、已分离人声、伴奏，创建任务时建议复制到：

```text
works/<work_id>/input/
```

不要直接引用外部路径跑完整流程。

路径策略：

| 类型 | 策略 |
|---|---|
| 用户输入音频 | 创建任务时复制到 `work_dir/input` |
| 模型文件 | 导入时复制到 `models` 目录 |
| runtime Python | 不复制，只保存路径 |
| ffmpeg | 不复制，只保存路径 |
| 输出作品 | 必须在 `works` 目录 |
| 删除操作 | 必须限制在数据目录内 |

好处：

- 用户移动原文件不影响任务
- 日志可复现
- 安全边界清晰

### 12.9 P0 页面范围

P0 页面只保留 5 个：

```text
/          首页 / 最近任务
/runtime   运行环境
/models    模型管理
/create    新建翻唱
/works     作品库
```

暂不做：

```text
/music
/model-hub
/editor
复杂 settings 页面
```

设置项先内嵌在 Runtime / Create 中，避免页面数量拖慢 P0。

### 12.10 React 前端实现约束

React 前端要薄，只负责：

- 表单
- 状态展示
- 任务轮询
- 调用 pywebview API

不要把核心业务判断写在前端。以下判断以后端返回为准：

- 能不能开始任务
- 缺什么依赖
- 模型是否可用
- 输入是否完整
- 当前任务是否可重试

推荐用 TanStack Query 处理状态轮询：

```text
running 时 1s 轮询
queue/running 继续轮询
done/failed/cancelled 停止轮询
```

推荐用 React Hook Form + Zod 处理：

- 运行环境路径配置
- 模型导入
- 输入模式
- 推理参数

前端做基础校验，后端做最终校验。

### 12.11 P0 导出格式

P0 导出格式不要贪多：

```text
WAV 必做
MP3 可选
FLAC 后置
```

先保证稳定生成和导出，再扩展格式。

### 12.12 P0 日志要求

每个任务至少记录：

- 输入文件
- 输入模式
- 使用模型
- 使用引擎
- 使用 Python 路径
- ffmpeg / ffprobe 路径
- CUDA / CPU 状态
- 每一步开始 / 结束
- 子进程 stdout / stderr
- 最终输出路径

失败时前端展示摘要，详情打开日志。

### 12.13 P0 实施顺序

```text
1. 基础桌面壳：React + pywebview + bridge
2. JSON 存储：settings / models / works
3. RuntimeManager：ffmpeg / SVC / RVC 检测与路径保存
4. ModelService：导入 SVC/RVC 模型
5. StemPreparer：song / vocals / stems 输入模式
6. InferenceRunner：真实调用 SVC/RVC
7. MixService：有伴奏混音，无伴奏输出干声
8. WorkService：串行队列、进度、日志、失败重试
9. 导出：WAV / MP3
```

P0 验收标准：

```text
用户能配置运行环境
→ 导入 SVC/RVC 模型
→ 选择完整歌曲或已分离人声
→ 生成 AI 人声
→ 有伴奏时混音
→ 导出结果
→ 失败时能看到明确原因
```

---

## 13. 复刻时最关键的文件参考

### 后端入口 / 桥接

- `app/main.py`
- `app/api/bridge.py`
- `app/config.py`

### 领域模型

- `app/domain/entities.py`
- `app/domain/audio_editor.py`
- `app/domain/enums.py`

### 存储

- `app/infrastructure/storage.py`
- `app/infrastructure/paths.py`

### 核心服务

- `app/application/work_service.py`
- `app/application/conversion_service.py`
- `app/application/model_service.py`
- `app/application/audio_editor_service.py`
- `app/application/music_service.py`
- `app/application/model_hub_service.py`
- `app/application/system_service.py`

### 引擎 / 工具

- `app/infrastructure/engine.py`
- `app/infrastructure/svc_engine.py`
- `app/infrastructure/rvc_engine.py`
- `app/infrastructure/uvr_tool.py`
- `app/infrastructure/ffmpeg_tool.py`
- `app/infrastructure/audio_engine.py`
- `app/infrastructure/*_worker.py`

### 前端（新项目 React 方案）

- `web/src/api/index.ts`
- `web/src/api/bridge.ts`
- `web/src/api/types.ts`
- `web/src/router/index.tsx`
- `web/src/pages/Home.tsx`
- `web/src/pages/Create.tsx`
- `web/src/pages/Models.tsx`
- `web/src/pages/Runtime.tsx`
- `web/src/pages/Works.tsx`
- `web/src/stores/*.ts`
- `web/src/components/AppHeader.tsx`

### 安装器

- `install/install.py`
- `setup_env.bat`
- `install_prereqs.bat`
- `installer/build.ps1`
- `installer/xb-svcb-app.spec`
- `installer/xb-svcb.iss`

---

## 14. `.gitignore` 复用建议

当前参考项目有 3 个 `.gitignore`：

```text
.gitignore
app/.gitignore
web/.gitignore
```

### 14.1 当前项目忽略内容提炼

根目录 `.gitignore` 主要忽略：

| 类别 | 内容 |
|---|---|
| Python 缓存 / 构建 | `__pycache__/`、`*.py[cod]`、`*.egg-info/`、`build/`、`dist/*`、`wheels/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/` |
| 虚拟环境 | `.venv/`、`.venv-*/`、`env/`、`venv/`、`app/.venv/` |
| 前端产物 | `node_modules/`、`web/dist/`、`web/dist-ssr/`、`*.local`、`.eslintcache`、`*.tsbuildinfo` |
| 大文件 | `*.pth`、`*.onnx`、`*.pt`、`*.ckpt`、音频文件 |
| 日志 | `logs/`、`*.log`、npm/yarn/pnpm debug log |
| IDE / OS | `.idea/`、`.vscode`、`.DS_Store`、`Thumbs.db`、`desktop.ini` |
| 生成环境 | `engines/`、`models/`、`.venv-svc/` |
| 本地数据 | `.xb-svcb/` |

当前项目还有一个特殊例外：

```gitignore
!assets/models/
!assets/models/**
```

这个例外用于把安装器自带底模 / UVR 模型纳入仓库或 Git LFS。

**VCA-Studio 不建议照搬这个例外**，因为新规划是：主安装包保持轻量，runtime / 模型资源独立管理。

### 14.2 VCA-Studio 推荐 `.gitignore`

建议根目录使用：

```gitignore
# ===== Python =====
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
build/
dist/
wheels/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# ===== Virtual envs =====
.venv/
.venv-*/
env/
venv/
app/.venv/

# ===== Frontend / Node =====
node_modules/
web/dist/
web/dist-ssr/
coverage/
*.local
.eslintcache
*.tsbuildinfo
*.timestamp-*-*.mjs

# ===== Runtime / generated AI env =====
runtime/
engines/
models/
.venv-svc/
.venv-rvc/
.venv-uvr/
.venv-hub/

# ===== User data =====
.vca_studio/
data_home.json

# ===== Large model / audio files =====
*.pth
*.onnx
*.pt
*.ckpt
*.safetensors
*.bin
*.index
*.npy
*.npz
*.mp3
*.wav
*.flac
*.m4a
*.ogg
*.aac

# ===== Logs =====
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# ===== IDE / Editor =====
.idea/
.vscode/*
!.vscode/extensions.json
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?

# ===== OS =====
.DS_Store
Thumbs.db
desktop.ini

# ===== Local scratch =====
.tmp/
```

关键差异：

- 不放行 `assets/models/**`
- 新增 `.vca_studio/`
- 新增 `runtime/`
- 新增 `.venv-rvc/`、`.venv-uvr/`、`.venv-hub/`
- 新增 `*.safetensors`、`*.index`、`*.npy`、`*.npz`

---

## 15. 主要风险点与产物体积说明

### 14.1 AI 依赖安装风险最高

So-VITS-SVC / RVC / fairseq / torch / numpy / pyworld 是最大不确定性。当前项目通过大量 Windows 特化逻辑规避，Mac 需要重新验证。

建议新项目先把 AI 环境当作“插件式 runtime”，不要打进主程序。

### 14.2 Mac 客户端不是简单换安装器

Mac 涉及：

- `.app` 可写目录问题
- Gatekeeper
- 签名 / notarization
- ffmpeg 分发
- Python / venv 安装
- torch CPU / MPS 兼容
- 子进程权限
- pywebview backend 差异

建议 Mac MVP 明确降低承诺：

> Mac 初版支持界面、模型管理、在线资源、作品库、音频编辑器、CPU 推理试验；CUDA 不支持。

### 14.3 ModelScope / 妖狐 API 是外部依赖

新项目需要考虑：

- API Key / token 本地保存
- 失败兜底
- QPS 限流
- 资源不可用提示
- 隐私说明

### 14.4 当前项目 release 产物为什么大

当前项目 release 大，核心原因不是代码和前端，而是 **AI 模型资源被打进安装包**。

主要来源：

1. **安装包内置底模和 UVR 模型**

   当前项目会把 `assets/models/` 放进安装包，里面包括：

   ```text
   checkpoint_best_legacy_500.pt
   nsf_hifigan/
   rmvpe.pt
   5_HP-Karaoke-UVR.pth
   UVR-DeEcho-DeReverb.pth
   ```

   这些权重文件本身就是 GB 级别，是安装包变大的最大原因。

2. **当前项目选择“自带优先”策略**

   也就是：

   ```text
   assets/models 有资源 → 安装时本地复制
   assets/models 缺失 → 再联网下载
   ```

   好处是用户安装后部署模型很快，坏处是安装包巨大。

3. **PyInstaller onedir 也会带 Python 运行时**

   `XB-SVCB.exe + _internal` 会包含：

   - Python 运行时
   - pywebview
   - pythonnet / clr_loader
   - bottle / proxy_tools
   - httpx / certifi
   - 前端 dist
   - worker 脚本

   但这部分不是最大头，最大头仍是模型权重。

4. **torch / fairseq 等 AI 重依赖没有打进主 exe**

   当前 PyInstaller spec 排除了：

   ```text
   torch
   librosa
   numpy
   audio_separator
   fairseq
   ```

   所以 release 大不是因为 torch 被打进主程序，而是因为模型资源被打进安装包。

#### VCA-Studio 分发建议

VCA-Studio 不建议照搬“主安装包内置模型资源”。

P0 分发方式：

```text
VCA-Studio-Setup.exe
只含软件本体
不含 SVC/RVC/UVR 模型
不含 torch
不含 so-vits-svc
```

运行环境通过软件内 Runtime Manager 处理：

```text
选择已有环境
导入整合包
在线安装作为兜底
```

后续如果要照顾小白用户，可以单独提供资源包：

```text
VCA-Studio-Runtime-SVC-cu121.zip
VCA-Studio-Runtime-RVC-cu118.zip
VCA-Studio-UVR-Models.zip
```

但不要塞进主安装包。

推荐目标：

```text
主安装包保持轻量
runtime / 模型资源独立管理
用户可导入整合包
在线下载只作为兜底
```

---

## 15. 推荐新项目架构

```text
VCA-Studio/
├─ app/
│  ├─ api/
│  ├─ application/
│  ├─ domain/
│  ├─ infrastructure/
│  ├─ config.py
│  └─ main.py
├─ web/
├─ install/
│  ├─ install.py              # 跨平台核心
│  ├─ setup-windows.bat
│  └─ setup-macos.sh
├─ installer/
│  ├─ windows/
│  │  ├─ build.ps1
│  │  └─ app.iss
│  └─ macos/
│     ├─ build.sh
│     ├─ app.spec
│     └─ entitlements.plist
├─ assets/
│  ├─ icon/
│  └─ models/
└─ README.md
```

核心原则：

- 业务代码跨平台
- 安装器分平台
- runtime 路径分平台
- AI 环境独立
- ffmpeg / Python / uv 检测抽象成函数，不散落在安装器里

---

## 16. 最小 MVP 定义

### MVP 1：桌面壳 + AI 翻唱核心闭环

- React + pywebview
- 运行环境检测
- 模型导入
- 输入模式：完整歌曲 / 已分离人声 / 人声+伴奏
- SVC / RVC 推理
- 有伴奏混音，无伴奏输出干声
- 导出结果
- 日志与失败原因

### MVP 2：多模型基础版

- LRC 导入
- 片段时间轴
- 逐句分配模型
- 多模型整轨推理
- 自动人声合并

### MVP 3：增强能力

- UVR 自动分离增强
- 合唱
- 可视化时间轴
- 音频编辑器
- 在线曲库
- ModelScope 模型站

这样风险最小。先跑通 AI 翻唱核心闭环，再扩展多模型、编辑器和生态功能。

---

## 17. 总结

当前项目本质是：

```text
React + Vite 前端
+ pywebview 桌面壳
+ Python 本地业务服务
+ JSON 本地存储
+ ffmpeg 音频处理
+ UVR 人声分离
+ So-VITS-SVC / RVC 推理子环境
+ ModelScope / 妖狐 API 外部服务
+ Windows 安装器
```

复刻新项目时，**最应该复用的是架构和功能边界**：

- `api → application → domain ← infrastructure`
- pywebview bridge
- JSON 本地仓储
- AI 子环境隔离
- EngineRegistry 多框架路由
- WorkService + ConversionService 队列
- AudioEditorService + FFmpegEngine 时间轴渲染
- ModelHub / MusicService 独立异步事件循环

新增 Mac 客户端时，**不要重写桌面技术栈**。最短路线是：保留 pywebview + Python 后端，前端使用 React + Vite + TypeScript，新增 macOS 打包、runtime 路径、安装脚本和依赖检测。

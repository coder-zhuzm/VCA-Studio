# VCA-Studio 实现路线关键补充方案

> 本文是对 `PROJECT_COPY_REPORT.md` 的补充，不替代原文档。  
> 目标：在保留原规划的基础上，明确 VCA-Studio 的阶段实现顺序，避免一开始复刻完整 XB-SVCB，优先跑通 AI 翻唱核心闭环，并将“多模型混唱”作为后续差异化核心。  
> 更新时间：2026-07-06

---

## 1. 总体原则

VCA-Studio 不建议一开始完整复刻 XB-SVCB 的所有功能。

推荐路线：

```text
先跑通单模型翻唱闭环
→ 再做多模型混唱
→ 再做时间轴编辑
→ 再做音频编辑器
→ 最后补模型站、在线曲库、自动安装器增强
```

核心原则：

1. **P0 只做最小可用闭环**
   - Runtime 检测
   - RVC 模型导入
   - 音频输入
   - 人声分离 / 已分离人声接入
   - RVC 推理
   - 混音
   - 作品库

2. **多模型混唱是 VCA 的差异化重点**
   - 不要只做另一个 RVC WebUI / AICoverGen。
   - 重点做歌词/片段时间轴、模型分配、合唱、自动拼接。

3. **LRC 的本质不是歌词显示，而是 Segment Timeline 的输入来源**
   - LRC 只是生成片段时间轴的一种方式。
   - 后续还可以支持手动切句、静音检测切句、AI 自动原唱解析。

4. **不要逐句碎片推理**
   - 多模型混唱应采用“每个模型整轨推理，再按片段裁切拼接”的策略。
   - 这样能减少电流声、咔哒声和短音频推理不稳定问题。

5. **Vocal to MIDI & Lyrics 是高级路线，不进 P0**
   - ACE Studio 类似功能应作为 P3/P4 的“原唱解析 / 人声转谱”能力。
   - 它服务于改词、修音、重唱换声和更精细的多模型编排。

---

## 2. 推荐阶段路线图

```text
阶段 0：桌面壳 + Runtime Manager
阶段 1：P0 单模型 RVC 翻唱闭环
阶段 2：So-VITS-SVC 接入
阶段 3：P1 多模型混唱 MVP
阶段 4：合唱与时间轴增强
阶段 5：Audio Editor Lite
阶段 6：Vocal to MIDI & Lyrics / 原唱解析
阶段 7：模型站 / 在线曲库 / 自动安装器增强
```

---

## 3. 阶段 0：桌面壳与 Runtime Manager

当前项目已基本完成：

```text
React + Vite + TypeScript
Ant Design
pywebview 桌面壳
前后端 bridge
浏览器 mock fallback
settings.json
/runtime 页面
ffmpeg / ffprobe / SVC / RVC / UVR 轻量检测
手动填写 runtime 路径
```

### 3.1 下一步关键补充

Runtime 检测需要从“路径存在”升级到“可执行 / 可 import / 可启动”。

建议检测项：

```text
ffmpeg:
  - 文件是否存在
  - ffmpeg -version 是否正常

ffprobe:
  - 文件是否存在
  - ffprobe -version 是否正常

RVC:
  - rvc_python 是否存在
  - python -c "import torch"
  - python -c "import rvc_python" 或实际使用模块
  - rvc_worker.py --check 可启动
  - 可选检测 hubert / rmvpe 底模

SVC:
  - svc_python 是否存在
  - sovits_repo 是否存在
  - inference/infer_tool.py 是否存在
  - python -c "import torch"
  - python -c "import librosa"
  - python -c "import fairseq"
  - svc_worker.py --check 可启动

UVR:
  - uvr_python 是否存在
  - python -c "import audio_separator"
  - uvr_model_dir 是否存在
  - 5_HP-Karaoke-UVR.pth 是否存在
  - UVR-DeEcho-DeReverb.pth 是否存在
```

统一状态模型：

```ts
interface RuntimeComponentStatus {
  key: 'ffmpeg' | 'ffprobe' | 'uvr' | 'svc' | 'rvc' | 'modelhub'
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

---

## 4. 阶段 1：P0 单模型 RVC 翻唱闭环

P0 目标：

```text
导入 RVC 模型
→ 选择输入音频
→ 准备人声与伴奏
→ RVC 推理
→ 混音
→ 生成作品
→ 试听 / 导出 / 查看日志
```

P0 暂不做：

```text
在线曲库
模型站
多模型混唱
音频编辑器
自动安装完整 AI runtime
Vocal to MIDI & Lyrics
```

---

### 4.1 模型管理

P0 只要求完整支持 RVC：

```text
RVC:
  - .pth 必填
  - .index 可选
```

需要实现：

```text
导入模型
删除模型
模型列表
模型健康检查
设置默认模型
模型元数据保存
```

建议模型元数据：

```json
{
  "id": "model_xxx",
  "name": "Model Name",
  "framework": "rvc",
  "files": {
    "checkpoint": "models/model_xxx/model.pth",
    "index": "models/model_xxx/model.index"
  },
  "params": {
    "default_transpose": 0,
    "default_index_rate": 0.75
  },
  "created_at": "2026-07-06T00:00:00Z"
}
```

So-VITS-SVC 可先预留字段，但不要求 P0 完整推理。

---

### 4.2 输入模式

P0 必须支持三种输入模式：

```text
1. 完整歌曲，自动分离
2. 已分离人声
3. 已分离人声 + 伴奏
```

前端文案：

```text
输入类型：
○ 完整歌曲，自动分离
○ 已分离人声
○ 已分离人声 + 伴奏
```

后端 payload 建议：

```ts
type InputMode = 'song' | 'vocals' | 'stems'

interface CreateCoverPayload {
  input_mode: InputMode
  source_path?: string | null
  vocals_path?: string | null
  instrumental_path?: string | null
  model_id: string
  params: Record<string, unknown>
  skip_dereverb?: boolean
}
```

---

### 4.3 统一人声准备函数

后端建议抽一个共用函数：

```python
def prepare_stems(work, work_dir, params, log_file):
    ...
    return PreparedStems(
        vocals_path=...,
        instrumental_path=...,
        duration=...
    )
```

逻辑：

```text
if input_mode == 'song':
    source = normalize_to_wav(source_path)
    vocals, instrumental = uvr.separate(source)
    if dereverb_enabled:
        vocals = uvr.dereverb(vocals)

elif input_mode == 'vocals':
    vocals = normalize_to_wav(vocals_path)
    instrumental = None
    if dereverb_enabled:
        vocals = uvr.dereverb(vocals)

elif input_mode == 'stems':
    vocals = normalize_to_wav(vocals_path)
    instrumental = normalize_to_wav(instrumental_path)
    if dereverb_enabled:
        vocals = uvr.dereverb(vocals)
```

注意：

- 跳过 UVR 分离可以，但不要跳过 WAV 规范化。
- 只有人声时，最终输出 AI 干声。
- 人声 + 伴奏时，建议校验两者时长差，但不要强制拒绝。
- 已分离人声默认 `skip_dereverb = true`，避免重复损伤音质。

---

### 4.4 RVC 推理

P0 最小参数：

```text
transpose
f0_method
index_rate
rms_mix_rate
protect
filter_radius
device
```

后端结构：

```text
InferenceService
→ EngineRegistry
→ RvcEngine
→ rvc_worker.py
→ output_ai_vocal.wav
```

统一引擎协议：

```python
class InferenceEngine:
    framework: str

    def available(self) -> bool:
        ...

    def infer(self, model, vocals_path, out_path, params, log_file):
        ...
```

---

### 4.5 混音

P0 混音规则：

```text
如果有 instrumental:
    AI vocals + instrumental → final.wav

如果没有 instrumental:
    final.wav = AI vocals
```

先只做 WAV 导出。

后续再补：

```text
MP3
FLAC
loudnorm
limiter
人声音量 / 伴奏音量
```

---

### 4.6 作品库与任务队列

P0 必须有任务队列，避免长任务阻塞 UI。

任务状态：

```text
pending
running
success
failed
cancelled
```

步骤：

```text
normalize
separate
dereverb
infer
mix
done
```

作品目录：

```text
.vca_studio/works/{work_id}/
├─ input/
├─ stems/
│  ├─ vocals.wav
│  └─ instrumental.wav
├─ inference/
│  └─ ai_vocal.wav
├─ output/
│  └─ final.wav
├─ run.log
└─ metadata.json
```

前端作品库 P0 功能：

```text
作品列表
状态 / 进度
试听 final.wav
试听 ai_vocal.wav
打开日志
打开目录
删除作品
失败重试
```

---

## 5. 阶段 2：So-VITS-SVC 接入

RVC P0 跑通后，再接 So-VITS-SVC。

模型要求：

```text
G_*.pth
config.json
可选 diffusion model
可选 diffusion config
```

参数：

```text
transpose
f0_predictor
speaker
cluster_ratio
shallow_diffusion
device
```

目标：

```text
EngineRegistry 真正支持多框架：
rvc
so-vits-svc
```

---

## 6. 阶段 3：P1 多模型混唱 MVP

这是 VCA 的差异化核心。

P1 目标：

```text
导入 LRC
→ 生成 Segment Timeline
→ 多模型分配
→ 每个模型整轨推理
→ 按片段裁切
→ 自动拼接
→ 与伴奏混音
```

---

### 6.1 Segment Timeline

LRC 只是时间轴来源之一，核心概念应是：

```text
Segment Timeline / 片段时间轴
```

Segment 数据结构建议：

```json
{
  "id": "seg_001",
  "start": 12.35,
  "end": 16.80,
  "text": "这一句歌词",
  "assigned_model_ids": ["model_a"],
  "mode": "solo",
  "fade_in": 0.03,
  "fade_out": 0.05,
  "metadata": {
    "source": "lrc"
  }
}
```

mode 可选：

```text
solo
choir
mute
original
```

---

### 6.2 LRC 导入

P1 只做本地 LRC：

```text
导入 .lrc
→ 解析时间戳
→ 生成 segments
→ 根据下一句 start 推断当前句 end
→ 支持整体 offset
```

P1 暂不做：

```text
在线歌词获取
AI 自动歌词识别
逐字歌词
```

---

### 6.3 多模型参数

每个模型独立参数：

```json
{
  "model_id": "model_a",
  "framework": "rvc",
  "params": {
    "transpose": 0,
    "f0_method": "rmvpe",
    "index_rate": 0.75,
    "protect": 0.33
  }
}
```

---

### 6.4 多模型渲染策略

不要逐句推理。

推荐策略：

```text
原始 vocals.wav
├─ 模型 A 整轨推理 → renders/model_a/full.wav
├─ 模型 B 整轨推理 → renders/model_b/full.wav
└─ 模型 C 整轨推理 → renders/model_c/full.wav

segments:
0-10s: A
10-20s: B
20-25s: A

裁切：
A_full[0-10]
B_full[10-20]
A_full[20-25]

拼接：
crossfade → merged_vocal.wav
```

优点：

```text
上下文连续
音色稳定
减少短片段噪声
减少咔哒声
方便合唱扩展
```

---

### 6.5 自动人声合并

P1 实现：

```text
按 segment 裁切对应模型 full.wav
相邻同模型片段合并
换人处 crossfade
未指派片段填静音或原始人声占位
输出 merged_vocal.wav
```

再与伴奏混音：

```text
merged_vocal.wav + instrumental.wav → final.wav
```

---

## 7. 阶段 4：合唱与时间轴增强

P1.5 / P2 做合唱。

合唱段数据：

```json
{
  "id": "seg_010",
  "start": 35.0,
  "end": 42.5,
  "text": "合唱这一句",
  "assigned_model_ids": ["model_a", "model_b"],
  "mode": "choir"
}
```

合唱算法：

```text
从每个模型 full.wav 裁同一段
每路乘以 1 / sqrt(N)
amix 叠加
alimiter 防爆音
生成 choir_segment.wav
```

时间轴增强：

```text
拖动片段边界
拆分片段
合并片段
删除片段
吸附歌词时间
时间轴缩放
批量指派模型
点击歌词跳转
```

---

## 8. 阶段 5：Audio Editor Lite

音频编辑器后置，不进入 P0/P1。

可参考 `waveform-playlist`：

```text
React
Web Audio
多轨
波形
clip 拖动
trim
fade
WAV 导出
annotations
```

VCA 首版编辑器目标：

```text
从作品创建编辑工程
多轨显示
导入音频
片段拖动
片段裁剪
音量
静音
淡入淡出
混音预览
导出 WAV
```

后续增强：

```text
真实波形缓存
声道 L/R/stereo
切口交叉淡化
undo/redo
局部重推理
MP3/FLAC
```

---

## 9. 阶段 6：Vocal to MIDI & Lyrics / 原唱解析

这是 ACE Studio 类似路线，作为高级功能，不进入 P0/P1。

ACE Studio 中该能力叫：

```text
Vocal to MIDI & Lyrics
```

VCA 中建议命名为：

```text
原唱解析
人声转谱
Vocal to MIDI & Lyrics
```

---

### 9.1 功能目标

完整流程：

```text
分离 vocals
→ 识别音高 / 节奏
→ 转 MIDI notes
→ 识别歌词 / 音素
→ 对齐到音符
→ 得到可编辑 MIDI + Lyrics
```

---

### 9.2 与 RVC/SVC 的关系

这个功能不是替代 RVC/SVC，而是提供更干净、可编辑的中间表示。

高级翻唱流程：

```text
原唱 vocals
→ Vocal to MIDI & Lyrics
→ Clear Guide Singer 重唱
→ RVC/SVC 换成目标音色
→ 与伴奏混音
```

---

### 9.3 两种翻唱模式

建议 VCA 后续明确区分：

| 模式 | 流程 | 适合 |
|---|---|---|
| 快速换声模式 | vocals → RVC/SVC | 快速翻唱，保留原唱表现 |
| 重唱换声模式 | vocals → MIDI + Lyrics → Guide Singer → RVC/SVC | 改词、修音、多模型精细编排 |

---

### 9.4 实现顺序

不要一开始追求 ACE Studio 级别效果。

建议顺序：

```text
P3.1 用户导入歌词 + 自动对齐
P3.2 F0 / pitch tracking 生成粗 MIDI
P3.3 Whisper / ASR 尝试歌词识别
P3.4 音符级歌词对齐
P3.5 用户手动修正
P3.6 Guide Singer 重唱
```

可研究方向：

```text
RMVPE / CREPE / torchcrepe / pyworld
Basic Pitch
Whisper / WhisperX
MFA forced alignment
DiffSinger / NNSVS / OpenUtau
```

---

## 10. 阶段 7：模型站、在线曲库、安装器增强

这些都后置。

### 10.1 模型站

先不做完整 ModelScope 模型站。

早期只做：

```text
本地模型导入
粘贴模型 zip 链接下载
下载后自动识别 .pth / .index
```

后续再做：

```text
ModelScope Provider
Hugging Face Provider
manifest 校验
模型上传
模型搜索
```

---

### 10.2 在线曲库

版权风险较高，后置。

P0/P1 只支持：

```text
本地音频导入
拖拽导入
用户自行准备素材
```

---

### 10.3 安装器增强

继续坚持：

```text
软件安装器
和
运行环境管理
分离
```

顺序：

```text
手动路径接入
→ 整合包目录扫描
→ 在线安装 / 修复
```

---

## 11. 更新后的最小开发清单

### P0 必做

```text
[x] Runtime 深度检测
[x] RVC 模型导入
[x] 三种输入模式
[x] _prepare_stems（当前为输入复制；创建时可选 ffmpeg WAV 规范化，长期做自动检测并提示转换）
[x] UVR 分离
[x] RVC 推理
[x] ffmpeg 最小混音（song / stems 模式 AI vocal + instrumental → final.wav）
[x] 作品库
[x] 串行任务队列（start_work 入队，后台单 worker 执行）
[x] 日志
[x] WAV 导出（导出已有 output/final.wav；真实生成待推理/混音接入）
```

### 当前 P0 进度确认（2026-07-08）

已完成可追踪的管理闭环：Runtime 路径与深度检测、模型导入与目录操作、三种输入模式创建 work、输入文件准备、UVR 人声/伴奏分离（`song` 模式，带去混响与失败降级）、RVC 推理、有伴奏混音、作品列表/详情/步骤/进度/日志、失败重试、删除、重命名、打开目录/日志、导出已有输出文件。

P0 单模型 RVC 翻唱闭环已跑通：`song` 完整歌曲 → UVR 分离 → RVC 推理 → 与伴奏混音；`vocals`/`stems` 已分离素材直推推理。下一步进入阶段 2：So-VITS-SVC 接入。

### 阶段 2 进度确认（2026-07-08）

已完成多框架推理引擎抽象：

- `infrastructure/engine.py`：`InferenceEngine` 协议 + `EngineRegistry` 按 `framework` 路由。
- `infrastructure/rvc_engine.py`：`RvcEngine`（原 `InferenceRunner` 的 RVC 逻辑下沉）。
- `infrastructure/svc_engine.py`：`SvcEngine`，调用 So-VITS-SVC 仓库 `inference/infer_tool.py`，支持 transpose / f0_predictor / method / speaker / cluster_ratio / shallow_diffusion，输出文件自动发现。
- `application/inference_runner.py`：改为按 `model.framework` 分发到对应引擎。
- `work_service`：放开框架限制（RVC / So-VITS-SVC），运行时按框架校验 `rvc` / `svc` 组件；`_params` 扩展 SVC 参数。
- `bridge`：装配 `EngineRegistry([RvcEngine, SvcEngine])`。

说明：`SvcEngine` 的 CLI 参数面向 So-VITS-SVC 4.1 `infer_tool`，需在真实安装环境下验证；`model` 导入（`G_*.pth` + `config.json` + 可选浅扩散）此前已支持。

### P1 必做

```text
[x] So-VITS-SVC 接入
[x] LRC 导入
[x] Segment Timeline
[x] 多模型选择
[x] 每模型独立参数
[x] 每模型整轨推理
[x] 按片段裁切
[x] crossfade 拼接（片段边缘 fade + concat）
[x] 多模型成品输出
```

### 阶段 3 进度确认（2026-07-08）

P1 多模型混唱 MVP 已落地：

- `application/lrc_parser.py`：LRC → 时间排序片段。
- `application/segment_builder.py`：片段归一化、默认模型分配、end 推断。
- `application/stitch_service.py`：按片段从各模型 `renders/<id>/full.wav` 裁切、边缘 fade、concat 拼接；支持 `solo`/`choir`(等响度叠加)/`mute`(静音)/`original`(原声)。
- `application/work_service.py`：`create_work` 接受 `models`（多模型+独立 params）与 `segments`；`_run_work` 逐模型整轨推理后拼接，再与伴奏混音；`_start_blocker` 校验所有指派模型与运行时。
- `InferenceRunner.run_rvc` 支持按模型指定输出路径。

说明：拼接采用片段边缘线性 fade + concat（非重叠 crossfade），已消除咔哒声；合唱为等响度 `amix`。前端 LRC/时间轴编辑 UI 与合唱增强留待阶段 4。

### P2 必做

```text
[x] 合唱段
[x] 等响度叠加（1/sqrt(N)）
[x] limiter（alimiter 防爆音）
[x] 局部重渲染（基于已有渲染重拼接）
[x] 时间轴拖拽（前端，片段列表编辑）
[x] 拆分/合并/删除片段（前端）
```

### 阶段 4 进度确认（2026-07-08）

合唱与时间轴增强后端已落地：

- `StitchService` 合唱段：从各模型裁同一段 → 每路 ×1/√N → `amix` 等响度叠加 → `alimiter` 防爆音；最终 `merged_vocal` 再统一过一次 `alimiter`。
- `WorkService.rerender_work`：对带时间轴的作品，基于 `renders/<id>/full.wav` 已有渲染直接重拼接（跳过推理），支持时间轴编辑后的局部重渲染；缺渲染缓存或无时间轴时给出明确错误。
- `bridge` 暴露 `rerender_work`。

说明：时间轴拖拽、拆分/合并/删除为前端对 `segments` 的编辑操作，后端已支持任意片段结构，无需改动；前端 UI 尚未实现。

### 阶段 5：Audio Editor Lite（2026-07-08）

前端音频编辑器 MVP 已落地（`web/src/pages/Editor.tsx`）：

- 路由 `/editor/:id`，作品库「编辑」入口进入。
- 片段时间轴可编辑：起始/结束、歌词、指派模型（多选）、模式（solo/choir/mute/original）、淡入淡出。
- 工具栏：添加片段、拆分选中、合并连续选中、删除选中、保存时间轴。
- 「局部重渲染」= 保存时间轴 + `rerender_work`；「整轨重渲染」= `start_work`。
- 后端新增 `update_work_segments`（`pending` 可编辑）、`bridge` 暴露；`DesktopApi`/mock/前端 `api` 同步。

说明：波形可视化、clip 拖动预览、音量包络仍属后续增强；当前以可编辑片段表 + 后端重渲染实现 MVP 闭环。

### 阶段 6：Vocal to MIDI & Lyrics / 原唱解析（2026-07-08）

高级路线 MVP（P3.2 音高追踪 + 歌词对齐）已落地：

- `infrastructure/pitch_analyzer.py`：自相关基频估计（ffmpeg 归一化到单声道 16k），逐帧估计 → 合并稳定音高区为粗 MIDI notes；无外部 ML 依赖，可用合成音频验证（440Hz → MIDI 69）。
- `align_lyrics`：导入歌词按音符时间跨度均匀对齐（naive 占位，待 WhisperX / MFA forced alignment）。
- `WorkService.analyze_work` / `set_work_lyrics`：解析结果存入 `work.analysis`（notes / lyrics / lyrics_aligned）。
- `bridge` 暴露 `analyze_work` / `set_work_lyrics`；Editor 页新增「原唱解析」面板（解析音高、导入并对齐歌词、展示音符与对齐结果）。

说明：当前为粗粒度自相关估计；后续可接入 RMVPE/CREPE/Basic Pitch 提升精度，ASR 做歌词识别，DiffSinger/NNSVS 做 Guide Singer 重唱。Guide Singer 重唱路线（P3.6）未做。

### P3 必做

```text
Audio Editor Lite
Vocal to MIDI & Lyrics 初版
Guide Singer 重唱路线验证
```

### P4 后置

```text
[x] 模型站（链接/ZIP 下载 + 自动识别）
在线曲库（版权风险，后置）
完整安装器（后置）
Mac 客户端（后置）
云端推理 Provider（后置）
```

### 阶段 7 进度确认（2026-07-08）

模型站 MVP 已落地（路线图早期目标）：

- `infrastructure/model_downloader.py`：支持 `http(s)` / `file` 链接下载，解包 zip 并自动识别 checkpoint / index / config / 浅扩散，推断框架（有 config.json → so-vits-svc，否则 rvc）。
- `ModelService.import_model_from_url`：下载→解包→复制识别文件→登记模型→校验。
- `bridge` 暴露 `import_model_from_url`；`Models` 页新增「从链接导入」面板。
- 测试覆盖 file:// 压缩包导入与框架识别。

说明：在线曲库（版权风险）、完整安装器、Mac 客户端、云端推理 Provider 按路线图后置，本轮未做。

---

## 12. 推荐最终定位

VCA-Studio 不应只是：

```text
RVC WebUI 桌面壳
```

而应定位为：

```text
桌面级 AI 翻唱编排工作台
```

核心差异化：

```text
单模型翻唱
+ 多模型混唱
+ 合唱叠声
+ 歌词/片段时间轴
+ 局部重渲染
+ 后期编辑
+ 后续 Vocal to MIDI & Lyrics 重唱换声
```
```

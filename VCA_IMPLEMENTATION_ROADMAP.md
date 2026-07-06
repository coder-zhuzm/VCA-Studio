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
Runtime 深度检测
RVC 模型导入
三种输入模式
_prepare_stems
UVR 分离
RVC 推理
ffmpeg 混音
作品库
任务队列
日志
WAV 导出
```

### P1 必做

```text
So-VITS-SVC 接入
LRC 导入
Segment Timeline
多模型选择
每模型独立参数
每模型整轨推理
按片段裁切
crossfade 拼接
多模型成品输出
```

### P2 必做

```text
合唱段
等响度叠加
limiter
时间轴拖拽
拆分/合并/删除片段
局部重渲染
```

### P3 必做

```text
Audio Editor Lite
Vocal to MIDI & Lyrics 初版
Guide Singer 重唱路线验证
```

### P4 后置

```text
模型站
在线曲库
完整安装器
Mac 客户端
云端推理 Provider
```

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

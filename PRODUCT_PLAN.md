# VCA-Studio 产品与技术规划（2026-07 起）

> 定位不变：**桌面级 AI 翻唱编排工作台**。
> 本文接替 `VCA_IMPLEMENTATION_ROADMAP.md` §11 的"下一步"部分，作为从当前 MVP 走向完整可用与长期演进的执行规划。
> 阶段完成标准沿用两级制：`[代码完成]` → `[真机验证]`，涉及外部 runtime 的能力必须过真机档。

---

## 0. 现状基线（2026-07-26）

**已完成（代码完成态）**
- 阶段 0–7 的 MVP 后端：单模型闭环、RVC/SVC 双引擎（真实接口 + device 传递）、UVR 分离（可降级）、多模型整轨推理、绝对时间轴拼接、合唱/limiter、局部重渲染、模型链接/ZIP 导入
- 作品全生命周期：创建/开始/取消/重试/删除/重命名/导出/日志/试听
- 崩溃恢复（启动对账 running→failed）、串行任务队列、长任务取消
- 前端 7 个页面 + mock fallback；测试 6 个文件全绿

**已知欠账（按风险排序）**
1. 🔴 全链路从未在真机（配好 RVC/SVC/UVR 的环境）验证
2. 🟠 原唱解析同步纯 Python：长音频卡 UI，实验性
3. 🟠 试听 base64 过桥：大文件内存高
4. 🟠 链接导入模型同步下载：阻塞 UI，无进度
5. 🟡 works.json 日志三重写放大；SVC 专项参数 UI 缺失；模型框架识别启发式弱

---

## 1. 里程碑总览

```text
M1  真机可用          （~1-2 周）  全链路真机验收 + 阻塞问题清零
M2  日常可用          （~2-4 周）  异步化、性能、体验补齐 → 自用无明显痛点
M3  编排完整版        （~1-2 月）  多模型 UI 完整、波形时间轴、批量工作流
M4  高级创作          （~2-3 月）  原唱解析正式版、Guide Singer 验证
M5  生态与分发        （远期）      安装器、模型站、打包分发、社区
```

原则依旧：**每个里程碑收口后再进下一个**；M1 未过，M2 以后一律不动手。

---

## 2. M1：真机可用（最高优先级，阻塞级）

目标：在目标机器（Windows i5-12400 + RTX 2060S；macOS Apple Silicon）上，
`song → UVR 分离 → RVC/SVC 推理 → 混音 → final.wav` 全链路跑通并能试听。

### 2.1 验收清单

```text
[ ] Windows CUDA：RVC 单模型 song 模式全链路（验证 -de cuda:0 生效，GPU 占用可见）
[ ] Windows CUDA：SVC 单模型 vocals 模式（svc_worker.py --check 先行）
[ ] macOS MPS：RVC 单模型 vocals 模式（mps 生效）
[ ] macOS CPU（Intel 或降级）：跑通一次确认 CPU 路径
[ ] UVR 分离：真实分离出人声/伴奏，dereverb 生效；失败降级路径确认
[ ] 多模型 + LRC：两个模型 + 时间轴，验证拼接对齐（听感：人声与伴奏无整体偏移）
[ ] 取消：推理中途取消，进程确实退出，状态 cancelled，可重试
[ ] 崩溃恢复：推理中强杀应用，重启后作品为 failed 可重试
```

### 2.2 预期修复项（真机必然暴露的问题）

- rvc-python / so-vits-svc 各版本参数差异（fork 兼容性）→ 记录实测版本，写入 README 支持矩阵
- 长路径 / 中文路径 / 空格路径（Windows 高发）
- `svc_worker.py` 在真实 4.1 fork 上的 kwargs 过滤实际效果
- UVR `audio_separator` 版本 API 差异

### 2.3 产出

- `docs/VERIFIED_MATRIX.md`：OS × 引擎 × 版本 实测矩阵（真机档案）
- 路线图勾选升级为 `[✓机]`

---

## 3. M2：日常可用（自用无痛点）

目标：一个普通用户（非开发者）从安装到出第一首翻唱 ≤ 30 分钟，日常操作无卡顿。

### 3.1 性能与异步（后端）

```text
[ ] 原唱解析异步化：analyze_work 走任务队列 + 前端轮询；
    numpy 向量化自相关（无 numpy 降级并限制 ≤60s 音频）
[ ] 试听流式化：pywebview 本地 HTTP 静态服务或自定义协议替代 base64 过桥；
    生成低码率 mp3 预览文件（output/preview.mp3）
[ ] import_model_from_url 走任务队列：进度回报（已下载字节/总大小）、可取消、超时
[ ] works.json 减重：logs 只保留尾部 N 条于 JSON，全量看 run.log；
    大字段（analysis.notes）落 work_dir 单独文件
[ ] 推理进度：解析引擎 stdout 里的进度信息（或按音频时长估算）更新 progress
```

### 3.2 体验补齐（前端）

```text
[ ] /create SVC 专项参数完整暴露（f0_predictor / speaker 下拉（读模型 config spk）/
    cluster / 浅扩散 + diffusion config）
[ ] /create 多模型 per-model 参数编辑（每模型折叠面板，非只有变调/Index）
[ ] /models 模型详情：spk 列表、采样率、大小、框架徽标；框架识别不确定时让用户确认
[ ] /works 队列可视化：排队位置、当前运行作品置顶
[ ] 全局错误提示规范化：引擎报错原文 + 一句话人话解释 + 指向 runtime 页的修复动作
[ ] 深色模式（Ant Design token，成本低）
```

### 3.3 稳定性

```text
[ ] 设置页"打开数据目录/清理孤儿 work 目录"（works.json 无记录的目录）
[ ] 磁盘空间预检：分离+多模型渲染前估算所需空间，不足则提示
[ ] 引擎健康自检入口：runtime 页一键跑 svc_worker --check / rvc 最小推理（3s 静音）
```

---

## 4. M3：编排完整版（差异化核心成型）

目标：多模型混唱从"API 可用"到"编排体验完整"，这是与 RVC WebUI 类产品拉开差距的一层。

### 4.1 波形时间轴编辑器（Editor 2.0）

```text
[ ] 波形渲染：人声轨 + 各模型渲染轨（wavesurfer.js 或自绘 Canvas，峰值缓存到 work_dir）
[ ] 片段可视化：色块按指派模型着色，拖动边界改 start/end，吸附 LRC 时间点
[ ] 点击播放定位、区间循环试听、A/B 对比（原唱 vs 某模型渲染）
[ ] 拆分/合并/删除在波形上直接操作；键盘快捷键
[ ] undo/redo（前端状态栈即可，保存时落库）
[ ] 音量包络（每片段 gain），拼接时应用
```

### 4.2 编排能力增强

```text
[ ] 批量指派：按选中片段/按奇偶句/按段落（verse/chorus 需人工标注）指派模型
[ ] 合唱增强：每路独立音量、声像（pan）左右分置；choir 段声部预览
[ ] 片段级变调覆盖（segment.params.transpose 覆盖模型默认）→ 拼接前重推该片段
[ ] 静音检测自动切句（ffmpeg silencedetect）作为无 LRC 时的时间轴来源
[ ] 时间轴模板：保存/套用编排方案到同一首歌的不同版本
```

### 4.3 工作流

```text
[ ] 作品复制（复用 stems 与渲染缓存，改编排出新版本）
[ ] 批量导出（多作品选中导出，MP3/FLAC 选项 + loudnorm）
[ ] 渲染缓存管理：renders/ 按模型参数 hash 命名，参数不变复用，变了重推
```

---

## 5. M4：高级创作（原唱解析正式版 + Guide Singer 验证)

目标：从"快速换声"进入"重唱换声"路线（路线图 §9 的两种模式正式分野）。

### 5.1 原唱解析正式版

```text
[ ] 音高：接入 RMVPE 或 torchcrepe（复用 RVC venv，避免新环境）；
    保留纯 Python 实现为无依赖 fallback
[ ] 歌词识别：Whisper（faster-whisper，独立可选组件，runtime 页可安装）
[ ] 对齐：WhisperX / 音素级强制对齐替代 naive 均匀铺开
[ ] MIDI 编辑器：钢琴卷帘只读预览 → 音符拖动编辑（后置）
[ ] 导出 MIDI + 对齐歌词（.mid / .lrc / .json）
```

### 5.2 Guide Singer 路线验证（P3.6，研究性质）

```text
[ ] 技术选型 spike：DiffSinger / NNSVS / OpenUtau 各跑一个 demo，
    评估：安装成本、音质、License、与现有 pipeline 契合度 → 写决策文档
[ ] MVP：解析出的 MIDI+歌词 → Guide Singer 合成干声 → 走既有 RVC/SVC 换声
[ ] 改词重唱：编辑歌词后重合成（差异化杀手锏，但依赖上面全部成立）
```

**风险声明**：M4 整体是研究向，允许失败；每个 spike 限时（如 1 周），不达预期即回退冻结，不拖累主线。

---

## 6. M5：生态与分发（远期）

```text
[ ] 一键安装包：PyInstaller/打包 + 首次启动向导（检测环境→引导安装 runtime）
[ ] Runtime 自动安装完整版：SVC / UVR 也纳入（现只有 RVC/ffmpeg）；
    整合包目录扫描识别
[ ] 模型站：ModelScope / Hugging Face Provider、manifest 校验、模型搜索与一键安装
[ ] 云端推理 Provider：本地无 GPU 时可选远程推理（接口抽象已具备：InferenceEngine）
[ ] 在线曲库：版权风险高，持续后置；只做"打开外部工具"级引导
[ ] 社区分享：编排方案（segments+params，不含音频/模型）导入导出与分享
[ ] i18n：中文优先，预留英文
```

---

## 7. 工程横切关注点（贯穿各里程碑）

```text
测试
[ ] M1 起：每修一个真机 bug 补一个回归测试
[ ] M2：WorkService 状态机专项测试（pending/running/cancelled/failed 全转移路径）
[ ] M3：Editor 前端引入 vitest（时间轴操作纯函数化后测试）

CI
[ ] GitHub Actions：Python 测试 + tsc + 前端 build（现在完全没有 CI）
[ ] 平台矩阵：ubuntu（逻辑测试）+ windows + macos（含 ffmpeg 的拼接测试）

架构守则
[ ] 引擎协议不扩散：新推理来源一律实现 InferenceEngine，禁止在 WorkService 特判
[ ] worker 模式统一：外部 Python 环境交互一律 worker 子进程 + 单行 JSON 协议
[ ] 数据迁移：works.json/models.json 加 schema_version 字段（M2 落地，为日后迁移留门）
```

---

## 8. 优先级速查（现在该做什么）

| 顺序 | 事项 | 里程碑 | 状态 |
|---|---|---|---|
| 1 | 真机全链路验收（Windows CUDA 优先） | M1 | ⬅️ **当前** |
| 2 | 真机暴露问题修复 + 支持矩阵文档 | M1 | |
| 3 | 原唱解析异步化 | M2 | 任务已建（#7） |
| 4 | 试听流式化 + 下载异步化 | M2 | |
| 5 | SVC/多模型参数 UI | M2 | |
| 6 | 波形时间轴编辑器 | M3 | |
| 7 | RMVPE/Whisper 接入 | M4 | |
| 8 | Guide Singer spike | M4 | |
| 9 | 安装器/模型站/分发 | M5 | |

---

*更新记录：2026-07-26 初版（基于当日代码审计与修复）。*

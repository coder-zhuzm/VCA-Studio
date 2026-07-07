# WorkService 最小任务队列骨架设计

日期：2026-07-07

## 背景

当前项目已经完成 Runtime Manager、ModelService 与 StemPreparer backend-only 第一版。StemPreparer 只负责三种输入模式的路径校验和文件复制，不负责 work metadata、队列、推理、混音或导出。

本阶段实现 WorkService 第一版：在后端创建 work 任务，调用 StemPreparer 准备输入，将任务 metadata 持久化到 JSON，并提供查询接口。该阶段不修改 Create 页面 UI，也不新增前端 API wrapper。

## 目标

- 创建 work 任务。
- 调用 StemPreparer 准备输入。
- 将 work metadata 持久化到 JSON。
- 查询 work 列表和单个 work。
- 保持 backend-only，不执行真实推理、混音、导出。
- 保留现有 `bridge.prepare_stems(payload)` 调试入口。

## 非目标

- 不做异步队列、线程、worker 或 JobRunner 抽象。
- 不做 UVR、RVC/SVC 推理、混音、导出。
- 不修改 Create / Works 页面 UI。
- 不新增前端 API wrapper 或 TypeScript 类型。
- 不引入数据库或正式测试框架。

## 架构

新增 `app/application/work_service.py`，保持现有分层：

- `StemPreparer`：输入校验与复制，返回 prepared files。
- `WorkService`：创建 work record、持久化、查询。
- `ListRepository`：JSON list 存储。
- `bridge.Api`：pywebview 薄封装，只转发方法。

配置新增：

```python
WORKS_DB = DATA_DIR / "works.json"
```

`build_api()` 中集中构造：

```python
stem_preparer = StemPreparer(config.WORKS_DIR)
work_service = WorkService(ListRepository(config.WORKS_DB), stem_preparer)
```

桥接层新增：

- `create_work(payload)`
- `list_works()`
- `get_work(work_id)`

同时保留：

- `prepare_stems(payload)`

## Work record 数据模型

第一版 work record 包含：

```json
{
  "id": "work_<12hex>",
  "name": "Untitled Work",
  "input_mode": "song",
  "input_files": [
    {
      "role": "input_song",
      "source_path": "/source/song.wav",
      "stored_path": "/app-data/works/work_x/input/song.wav",
      "filename": "song.wav"
    }
  ],
  "status": "pending",
  "stage": "prepared",
  "logs": [
    {
      "level": "info",
      "message": "Input prepared",
      "created_at": "2026-07-07T00:00:00Z"
    }
  ],
  "created_at": "2026-07-07T00:00:00Z",
  "updated_at": "2026-07-07T00:00:00Z"
}
```

字段语义：

- `id`：复用 StemPreparer 生成的 `work_<12hex>`。
- `name`：来自 payload；为空时使用 `Untitled Work`。
- `input_mode`：`song`、`vocals` 或 `stems`。
- `input_files`：来自 StemPreparer 返回的文件列表，记录源路径、存储路径、角色与文件名。
- `status`：第一版只使用 `pending`，保留 `failed` 作为内部异常状态。
- `stage`：成功创建后固定为 `prepared`。
- `logs`：第一版只写一条输入准备完成日志。

## 创建流程

`WorkService.create_work(payload)`：

1. 标准化 `payload`，空值按 `{}` 处理。
2. 读取 `name`，若为空则使用 `Untitled Work`。
3. 调用 `StemPreparer.prepare(payload)`。
4. 如果 StemPreparer 返回 `ok=false`：
   - 返回 `{ "ok": false, "error": ... }`。
   - 不写入 work record。
5. 如果准备成功：
   - 使用返回的 `work_id`、`mode`、`files` 组装 work record。
   - 写入 `ListRepository(config.WORKS_DB)`。
   - 返回 `{ "ok": true, "work": record }`。

成功创建后固定：

- `status = "pending"`
- `stage = "prepared"`

## 查询流程

`list_works()`：

```python
{"ok": True, "works": repo.all()}
```

顺序复用 `ListRepository.add()` 的 newest-first 行为。

`get_work(work_id)`：

- 找到时返回 `{ "ok": true, "work": record }`。
- 找不到时返回 `{ "ok": false, "error": "Work not found" }`。

## 错误处理

遵循现有 service 风格：

- 用户输入错误返回 `{ "ok": false, "error": "..." }`，不抛到 bridge。
- StemPreparer 失败时透传错误，不写入 JSON。
- JSON 写入或内部异常时返回 `ok=false`。
- 如果输入已准备但 record 写入失败，WorkService 可尽力清理刚创建的 work 目录；清理失败不覆盖主错误。

## 验证计划

本阶段只验证后端：

1. 静态编译：

```bash
python3 -m py_compile app/application/work_service.py app/api/bridge.py app/config.py
```

2. 后端 smoke：

- 使用临时目录创建 fake input files。
- 构造 `StemPreparer + WorkService + ListRepository`。
- 验证 `create_work(song)` 成功。
- 验证 record 写入 JSON。
- 验证 `list_works()` 返回该 work。
- 验证 `get_work(id)` 返回该 work。
- 验证缺失输入文件时 `ok=false`。
- 验证失败时 `WORKS_DB` 不新增 record。

3. 不运行前端 build，因为本阶段不改前端。

## 后续扩展

未来真实队列阶段可以在不破坏本设计的基础上扩展：

- `status` 增加 `running`、`completed`、`cancelled`。
- `stage` 增加 `queued`、`inferencing`、`mixing`、`exporting`。
- 追加日志与失败原因。
- 引入 worker/runner 抽象。
- 前端 Create flow 改为调用 `create_work()`。

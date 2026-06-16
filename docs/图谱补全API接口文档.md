# 图谱补全（Graph Augmentation）API 接口文档

---

服务器
http://10.253.50.113:8080/

## 一、背景与概述

**图谱补全**功能允许用户输入一段新闻文本，系统将自动通过以下流水线步骤将新闻中涉及的事件与影响关系补充进知识图谱：

```
新闻输入 → 实体抽取 → 相似度匹配 → 链路生成 → LLM补全 → 人工审核 → 写入图谱
```

具体阶段说明：

| 阶段 | 英文标识 | 说明 |
|------|---------|------|
| 实体抽取 | `extract` | 用 LLM 从新闻中抽取关键事件与变量变化 |
| 相似度匹配 | `similarity` | 用 Embedding 将抽取结果与图谱现有节点进行余弦相似度匹配 |
| LLM 语义复核 | `similarity_audit` | （可选）再次用 LLM 对 Embedding 候选结果进行语义复核 |
| 链路生成 | `chains` | 根据匹配到的节点，在图谱中查找相关影响链路 |
| 图谱补全 | `augment` | 将新闻信息与图谱链路上下文输入 LLM，生成新的图谱 JSON |
| 人工审核 | `review` | 人工审查 LLM 输出的图谱路径，确认或修改后批准 |
| TTL 转换 | `ttl` | 审核通过后将图谱 JSON 转为 TTL 格式并写入知识图谱 |

当前版本图结构约束：

- 节点类型固定为 `Event`、`MarketVariable`、`VariableChange`、`ValuationOutcome`
- 业务关系固定为 `causes`
- `VariableChange` 必须通过节点字段 `for_variable` 绑定到对应 `MarketVariable`


self-growing知识库


---

## 二、接口总览

| 功能模块 | 方法 | 路径 | 说明 |
|---------|------|------|------|
| **运行管理** | POST | `/api/augment/run` | 启动补全任务（输入新闻） |
| | GET | `/api/augment/runs` | 获取历史任务列表 |
| | GET | `/api/augment/status` | 查询任务状态 |
| | GET | `/api/augment/artifact` | 获取任务中间产物文件 |
| | GET | `/api/augment/stream` | SSE 实时进度流 |
| | POST | `/api/augment/delete` | 删除任务 |
| | GET | `/api/augment/workflow` | 获取工作流程图 |
| **人工审核** | GET | `/api/augment/review/paths` | 获取补全路径列表 |
| | GET | `/api/augment/review/node-options` | 获取节点候选列表 |
| | POST | `/api/augment/review/paths/save` | 保存路径选择 |
| | GET | `/api/augment/review/graph` | 获取审核图谱 |
| | POST | `/api/augment/review/save` | 保存审核后的图谱 JSON |
| | POST | `/api/augment/review/approve` | 批准审核（写入图谱） |
| | POST | `/api/augment/review/reject` | 拒绝审核 |
| **激活管理** | GET | `/api/augment/ttl/active` | 查看当前激活的补全 TTL |
| | POST | `/api/augment/ttl/active` | 设置激活的补全 TTL |
| **设置** | GET | `/api/settings/augment` | 获取补全参数配置 |
| | POST | `/api/settings/augment` | 修改补全参数配置 |
| | GET | `/api/settings/models` | 获取可用模型列表 |

---

## 三、公共约定

### 3.1 Base URL

```
http://<服务器IP>:<端口>
```

默认对外端口：`8080`（当前部署通过前端 Nginx 反向代理统一暴露 `/api/*` 接口）

### 3.2 请求格式

- POST 请求 Body 默认使用 `application/json`
- 以下接口额外支持 `text/plain`：
  - `POST /api/augment/run`
  - `POST /api/augment/review/save`
  - `POST /api/augment/review/reject`
- GET 请求参数通过 URL Query String 传递

### 3.3 响应格式

- 大多数接口返回 `application/json`
- `GET /api/augment/artifact`：
  - 当 `name` 为 `.json` 文件时返回 `application/json`
  - 当 `name` 为 `.txt`、`.ttl` 等文本文件时返回 `text/plain`
- `GET /api/augment/stream` 返回 `text/event-stream`
- 成功响应：HTTP 200，body 包含业务数据
- 失败响应：HTTP 4xx/5xx，body 格式：
  ```json
  { "error": "错误说明" }
  ```

### 3.4 runId 格式

系统自动生成，格式示例：

```
run_20260319_143022_123_ab3f
```

---

## 四、接口详细说明

---

### 4.1 启动补全任务

**接口说明：** 输入一段新闻文本，异步启动图谱补全流水线，立即返回 `runId`。

```
POST /api/augment/run
Content-Type: application/json
```

#### 请求 Body

```json
{
  "newsText": "美联储宣布加息50个基点，市场普遍预期此举将抑制通胀压力，但同时引发对经济衰退的担忧。美股三大指数全线下跌，债券收益率大幅攀升。"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `newsText` | string | 是 | 新闻正文，最大 200,000 字符 |

> 也支持直接传纯字符串 body（Content-Type: text/plain），系统会将整个 body 当作新闻文本。

#### 响应示例

```json
{
  "runId": "run_20260319_143022_123_ab3f"
}
```

#### 错误码

| HTTP 状态 | 说明 |
|-----------|------|
| 400 | `newsText` 为空或超过 200,000 字符限制 |
| 500 | 服务内部错误 |

#### 测试示例（curl）

```bash
curl -X POST http://localhost:8080/api/augment/run \
  -H "Content-Type: application/json" \
  -d '{
    "newsText": "美联储宣布加息50个基点，市场普遍预期此举将抑制通胀压力，但同时引发对经济衰退的担忧。美股三大指数全线下跌，债券收益率大幅攀升。"
  }'
```

---

### 4.2 查询任务状态

**接口说明：** 轮询任务执行进度和当前状态。

```
GET /api/augment/status?runId={runId}
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `runId` | string | 是 | 任务 ID |

#### 响应字段说明

```json
{
  "runId": "run_20260319_143022_123_ab3f",
  "status": "WAITING_REVIEW",
  "stage": "review",
  "startedAt": "2026-03-19T14:30:22.000Z",
  "updatedAt": "2026-03-19T14:32:45.000Z",
  "reviewed": false,
  "idPrefix": "aug_a1b2c3d4e5_",
  "artifact_extract_raw": "01_extract_raw.txt",
  "artifact_extract": "01_extract.json",
  "artifact_similarity_raw": "02_similarity_embedding_raw.json",
  "artifact_similarity_audit": "02_similarity_audit.json",
  "artifact_similarity_audit_raw": "02_similarity_audit_raw.txt",
  "artifact_similarity_filtered": "02_similarity.json",
  "artifact_similarity": "02_similarity_compact.json",
  "artifact_chains": "03_chains.json",
  "artifact_chains_compact": "03_chains_compact.json",
  "artifact_llm_raw": "04_llm_raw.txt",
  "artifact_normalized": "05_normalized.json",
  "similarityAudit": {
    "enabled": true,
    "modelId": "model/chatGPT5.2.json",
    "reviewedQueries": 3,
    "droppedCount": 1,
    "totalQueries": 3,
    "emptyTopQueries": 0,
    "fallbackUsed": false
  },
  "settings": {
    "extractModelId": "model/Qwen3-235b-a22b.json",
    "augmentModelId": "model/chatGPT5.2.json",
    "autoLoad": true
  }
}
```

#### status 枚举值

| 值 | 说明 |
|----|------|
| `RUNNING` | 流水线正在执行中 |
| `WAITING_REVIEW` | 等待人工审核 |
| `COMPLETED` | 已完成并写入图谱 |
| `FAILED` | 执行失败（见 `error` 字段） |
| `REJECTED` | 人工审核被拒绝（见 `error` 字段） |

#### stage 枚举值（流水线当前阶段）

| 值 | 说明 |
|----|------|
| `extract` | 实体抽取中 |
| `similarity` | 相似度匹配中 |
| `chains` | 链路生成中 |
| `augment` | LLM 补全中 |
| `review` | 等待审核 |
| `ttl` | TTL 转换中 |
| `load` | 兼容保留阶段值 |
| `done` | 全部完成 |

> 说明：当前实现中审批通过后通常从 `ttl` 直接进入 `done`，不会长期停留在 `load`。

#### 错误码

| HTTP 状态 | 说明 |
|-----------|------|
| 400 | `runId` 缺失或格式非法 |
| 404 | 任务不存在 |

#### 测试示例（curl）

```bash
curl "http://localhost:8080/api/augment/status?runId=run_20260319_143022_123_ab3f"
```

---

### 4.3 实时进度流（SSE）

**接口说明：** 通过 Server-Sent Events（SSE）实时接收任务执行过程中的思考文本与阶段完成通知，适合前端实时展示。

```
GET /api/augment/stream?runId={runId}
Accept: text/event-stream
```

**说明：** 连接建立时，系统会立即发送三个 snapshot 事件（已完成的历史思考内容快照），随后持续推送增量事件。

#### SSE 事件类型

| event 字段 | data 内容 | 说明 |
|-----------|-----------|------|
| `extract_thinking_snapshot` | 字符串（可为空） | 连接时推送：抽取阶段思考内容历史快照 |
| `similarity_audit_thinking_snapshot` | 字符串（可为空） | 连接时推送：相似度复核思考内容历史快照 |
| `augment_thinking_snapshot` | 字符串（可为空） | 连接时推送：补全阶段思考内容历史快照 |
| `extract_thinking_delta` | 增量文本片段 | 抽取阶段实时思考内容增量 |
| `similarity_audit_thinking_delta` | 增量文本片段 | 相似度复核阶段实时思考内容增量 |
| `augment_thinking_delta` | 增量文本片段 | 补全阶段实时思考内容增量 |
| `extract_done` | 空字符串 | 抽取阶段完成通知 |
| `similarity_audit_done` | 空字符串 | 相似度复核阶段完成通知 |
| `augment_done` | 空字符串 | 补全阶段完成通知 |

> **注意：** 阶段完成事件的 event 名格式为 `{阶段名}_done`，data 为空字符串。不存在名为 `step_done` 的事件类型。

#### SSE 响应格式示例

```
event: extract_thinking_snapshot
data:

event: similarity_audit_thinking_snapshot
data:

event: augment_thinking_snapshot
data:

event: extract_thinking_delta
data: 正在分析新闻中的关键实体...

event: extract_thinking_delta
data: 识别到：美联储加息、美股下跌

event: extract_done
data:

event: augment_thinking_delta
data: 根据图谱链路，识别出以下影响路径...

event: augment_done
data:

: keepalive
```

#### 测试示例（curl）

```bash
curl -N "http://localhost:8080/api/augment/stream?runId=run_20260319_143022_123_ab3f" \
  -H "Accept: text/event-stream"
```

> `-N` 参数禁用缓冲，确保实时输出。

---

### 4.4 获取任务列表

**接口说明：** 获取历史补全任务列表，按时间倒序排列。

```
GET /api/augment/runs?limit={limit}&inputKeyword={keyword}
```

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | integer | 否 | 100 | 最多返回条数，上限 500 |
| `inputKeyword` | string | 否 | - | 按新闻文本关键词过滤（大小写不敏感） |

#### 响应示例

```json
{
  "runs": [
    {
      "runId": "run_20260319_143022_123_ab3f",
      "dir": "run_20260319_143022_123_ab3f",
      "status": "WAITING_REVIEW",
      "stage": "review",
      "startedAt": "2026-03-19T14:30:22.000Z",
      "updatedAt": "2026-03-19T14:32:45.000Z",
      "reviewed": false,
      "persistedTtl": null,
      "artifact_ttl": null,
      "hasTtl": false,
      "autoLoad": true
    },
    {
      "runId": "run_20260318_101500_002_cd5e",
      "dir": "run_20260318_101500_002_cd5e",
      "status": "COMPLETED",
      "stage": "done",
      "startedAt": "2026-03-18T10:15:00.000Z",
      "updatedAt": "2026-03-18T10:22:30.000Z",
      "reviewed": true,
      "persistedTtl": "/data/ontology/augmented/run_20260318_101500_002_cd5e.ttl",
      "artifact_ttl": "06_output.ttl",
      "hasTtl": true,
      "autoLoad": true
    }
  ]
}
```

#### 测试示例（curl）

```bash
# 获取最近 10 条记录
curl "http://localhost:8080/api/augment/runs?limit=10"

# 按关键词过滤
curl "http://localhost:8080/api/augment/runs?inputKeyword=美联储"
```

---

### 4.5 获取任务中间产物

**接口说明：** 下载或查看任务各阶段的中间产物文件，便于调试与分析。

```
GET /api/augment/artifact?runId={runId}&name={fileName}
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `runId` | string | 是 | 任务 ID |
| `name` | string | 是 | 文件名（见下表） |

#### 可用产物文件

| 文件名 | 格式 | 阶段 | 说明 |
|--------|------|------|------|
| `01_extract_raw.txt` | 文本 | 抽取 | LLM 抽取阶段的原始输出（含思考过程） |
| `01_extract.json` | JSON | 抽取 | 规范化后的实体抽取结果 |
| `02_similarity_embedding_raw.json` | JSON | 相似度 | Embedding 相似度匹配的原始结果 |
| `02_similarity_audit.json` | JSON | 相似度 | LLM 语义复核结果 |
| `02_similarity_audit_raw.txt` | 文本 | 相似度 | LLM 语义复核的原始输出 |
| `02_similarity.json` | JSON | 相似度 | 最终相似度过滤结果（用于链路检索） |
| `02_similarity_compact.json` | JSON | 相似度 | 精简版相似度（用于 Prompt 输入） |
| `03_chains.json` | JSON | 链路 | 图谱链路检索结果 |
| `03_chains_compact.json` | JSON | 链路 | 精简版链路（用于 Prompt 输入） |
| `04_llm_raw.txt` | 文本 | 补全 | LLM 补全阶段的原始输出（含思考过程） |
| `05_normalized.json` | JSON | 补全 | 规范化后的补全图谱 JSON（五数组结构：四类节点 + `relationships`） |
| `05_review_selection.json` | JSON | 审核 | 已保存的路径选择 |
| `05_reviewed.json` | JSON | 审核 | 最终审核确认的图谱 JSON |
| `06_output.ttl` | TTL | 完成 | 生成的知识图谱 TTL 文件 |

#### 响应格式

- `.json` 文件：返回 `application/json`
- 其他文件（`.txt`、`.ttl`）：返回 `text/plain`

#### 关键产物结构示例

**`01_extract.json`** — 实体抽取结果（包含 summary、notes、main_events、main_variable_changes 四个字段）：

```json
{
  "summary": "美联储加息引发市场动荡",
  "main_events": [
    "美联储加息50个基点",
    "美股三大指数下跌"
  ],
  "main_variable_changes": [
    "联邦基金利率上升",
    "股票市场指数下降",
    "债券收益率上升"
  ],
  "notes": []
}
```

**`05_normalized.json`** — LLM 补全生成的图谱 JSON（审核前），包含五个数组（四类节点 + `relationships`）：

```json
{
  "events": [
    {
      "id": "aug_a1b2c3d4e5_E001",
      "label": "美联储加息"
    }
  ],
  "market_variables": [
    {
      "id": "FederalFundsRate",
      "label": "联邦基金利率"
    }
  ],
  "variable_changes": [
    {
      "id": "aug_a1b2c3d4e5_VC001",
      "label": "联邦基金利率上升",
      "direction": "up",
      "for_variable": "FederalFundsRate"
    }
  ],
  "valuation_outcomes": [
    {
      "id": "aug_a1b2c3d4e5_Out001",
      "label": "融资成本上升",
      "direction": "up"
    }
  ],
  "relationships": [
    {
      "source": "aug_a1b2c3d4e5_E001",
      "target": "aug_a1b2c3d4e5_VC001",
      "relation": "causes"
    },
    {
      "source": "aug_a1b2c3d4e5_VC001",
      "target": "aug_a1b2c3d4e5_Out001",
      "relation": "causes"
    }
  ]
}
```

> 五个数组：`events`（事件）、`market_variables`（市场变量）、`variable_changes`（变量变化）、`valuation_outcomes`（估值结果）、`relationships`（关系）。
>
> 说明：
> - 当前运行时 `relationships[].relation` 的业务关系值固定为 `causes`
> - `VariableChange` 与 `MarketVariable` 的绑定通过节点字段 `for_variable` 表达，不单独计入业务关系数组

#### 测试示例（curl）

```bash
# 查看抽取结果
curl "http://localhost:8080/api/augment/artifact?runId=run_20260319_143022_123_ab3f&name=01_extract.json"

# 查看 LLM 补全后的图谱（五数组结构：四类节点 + relationships）
curl "http://localhost:8080/api/augment/artifact?runId=run_20260319_143022_123_ab3f&name=05_normalized.json"

# 查看 LLM 原始输出（含思考过程）
curl "http://localhost:8080/api/augment/artifact?runId=run_20260319_143022_123_ab3f&name=04_llm_raw.txt"
```

---

## 五、人工审核接口

> 说明：
> - 读取类接口（如 `review/paths`、`review/graph`、`review/node-options`）在 `05_normalized.json` 产出后即可使用
> - 写入类接口（`review/paths/save`、`review/save`、`review/approve`、`review/reject`）要求运行处于 `WAITING_REVIEW`

---

### 5.1 获取补全路径列表

**接口说明：** 获取审核候选路径。系统会先从标准化图中枚举路径，优先返回包含本次新增节点（`idPrefix` 开头）的候选路径；若不存在此类路径，则返回全部候选路径。若没有到达 `ValuationOutcome` 的完整路径，则回退返回从 `Event` 出发的可达终止路径。最多枚举 120 条。

```
GET /api/augment/review/paths?runId={runId}
```

#### 响应字段说明

```json
{
  "runId": "run_20260319_143022_123_ab3f",
  "displayRunId": "run_20260319_143022_123_ab3f",
  "idPrefix": "aug_a1b2c3d4e5_",
  "reviewed": false,
  "paths": [
    {
      "id": "PATH_3f8a2b1c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a",
      "custom": false,
      "included": true,
      "hasNew": true,
      "text": "美联储加息 → 联邦基金利率上升 → 融资成本上升",
      "nodes": [
        { "id": "aug_a1b2c3d4e5_E001", "label": "美联储加息", "type": "Event", "direction": "" },
        { "id": "aug_a1b2c3d4e5_VC001", "label": "联邦基金利率上升", "type": "VariableChange", "direction": "up" },
        { "id": "aug_a1b2c3d4e5_Out001", "label": "融资成本上升", "type": "ValuationOutcome", "direction": "up" }
      ],
      "relationships": [
        { "source": "aug_a1b2c3d4e5_E001", "target": "aug_a1b2c3d4e5_VC001", "relation": "causes" },
        { "source": "aug_a1b2c3d4e5_VC001", "target": "aug_a1b2c3d4e5_Out001", "relation": "causes" }
      ]
    }
  ],
  "includedPathIds": [
    "PATH_3f8a2b1c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a"
  ],
  "stats": {
    "allPaths": 5,
    "newPaths": 3,
    "candidates": 3,
    "customPaths": 0
  }
}
```

#### 关键字段说明

| 字段 | 说明 |
|------|------|
| `paths[].id` | 路径唯一标识，格式为 `PATH_` + 64位 SHA256 十六进制字符串 |
| `paths[].custom` | 是否为手动自定义路径（`false` = LLM生成，`true` = 手工添加） |
| `paths[].included` | 当前是否已选中（包含在审核中） |
| `paths[].hasNew` | 路径中是否包含本次补全新增的节点（idPrefix 开头）|
| `paths[].text` | 路径的文字描述（节点 label 用 ` → ` 连接） |
| `stats.allPaths` | 完整枚举的路径总数 |
| `stats.newPaths` | 含新节点的路径数 |
| `stats.candidates` | 实际返回在 `paths` 字段中的候选路径数（优先展示含新节点的路径） |
| `stats.customPaths` | 手动自定义路径数 |
| `includedPathIds` | 当前已选中的路径 ID 列表（首次获取时默认全选） |

#### 测试示例（curl）

```bash
curl "http://localhost:8080/api/augment/review/paths?runId=run_20260319_143022_123_ab3f"
```

---

### 5.2 保存路径选择

**接口说明：** 选择接受哪些补全路径，并可添加自定义路径。调用此接口后系统会生成 `05_reviewed.json`。

```
POST /api/augment/review/paths/save?runId={runId}
Content-Type: application/json
```

#### 请求 Body

```json
{
  "includedPathIds": [
    "PATH_3f8a2b1c9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a",
    "PATH_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"
  ],
  "customPaths": [
    {
      "id": "my_custom_path_001",
      "nodes": [
        { "id": "aug_a1b2c3d4e5_E001", "label": "美联储加息", "type": "Event" },
        { "id": "aug_a1b2c3d4e5_Out002", "label": "美股下跌", "type": "ValuationOutcome", "direction": "down" }
      ],
      "relationships": [
        { "source": "aug_a1b2c3d4e5_E001", "target": "aug_a1b2c3d4e5_Out002", "relation": "causes" }
      ]
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `includedPathIds` | string[] | 是 | 选中的路径 ID 列表（空数组表示全不选） |
| `customPaths` | object[] | 否 | 手动新增的路径列表（每条路径需有 `id`、`nodes`、`relationships`） |

**customPaths 中每条路径的字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 自定义路径 ID（自行命名，不超过 200 字符） |
| `nodes` | object[] | 否 | 路径包含的节点（字段：`id`, `label`, `type`, `direction`, `for_variable`）。若节点类型为 `VariableChange`，必须提供 `for_variable` |
| `relationships` | object[] | 否 | 路径包含的关系（字段：`source`, `target`, `relation`, `strength`, `logic_type`, `and_group_id`）。业务关系当前仅支持 `causes`；如需补充 `VariableChange` 与 `MarketVariable` 的绑定，可额外提供 `forVariable` 辅助关系 |

> 当前运行时不支持旧版本多关系名（如 `causesChange`、`propagatesChange`、`affectsValuation` 等）；提交后不会保留这些关系值。

#### 响应示例

```json
{ "ok": true }
```

#### 测试示例（curl）

```bash
curl -X POST "http://localhost:8080/api/augment/review/paths/save?runId=run_20260319_143022_123_ab3f" \
  -H "Content-Type: application/json" \
  -d '{
    "includedPathIds": ["PATH_3f8a2b1c..."],
    "customPaths": []
  }'
```

---

### 5.3 获取审核图谱

**接口说明：** 获取可视化审核图谱数据（节点 + 边），用于图谱渲染展示。若已调用过 `paths/save` / `review/save`，则优先返回已保存的 `05_reviewed.json`；否则基于 `05_normalized.json` 现算。返回中的 `edges` 为展示结构，除业务关系边外还会自动补出 `forVariable` 辅助边。

```
GET /api/augment/review/graph?runId={runId}
```

#### 响应示例

```json
{
  "runId": "run_20260319_143022_123_ab3f",
  "displayRunId": "run_20260319_143022_123_ab3f",
  "nodes": [
    { "id": "aug_a1b2c3d4e5_E001", "label": "美联储加息", "type": "Event" },
    { "id": "FederalFundsRate", "label": "联邦基金利率", "type": "MarketVariable" },
    { "id": "aug_a1b2c3d4e5_VC001", "label": "联邦基金利率上升", "type": "VariableChange", "direction": "up", "for_variable": "FederalFundsRate" },
    { "id": "aug_a1b2c3d4e5_Out001", "label": "融资成本上升", "type": "ValuationOutcome", "direction": "up" }
  ],
  "relationships": [
    { "source": "aug_a1b2c3d4e5_E001", "target": "aug_a1b2c3d4e5_VC001", "relation": "causes" },
    { "source": "aug_a1b2c3d4e5_VC001", "target": "aug_a1b2c3d4e5_Out001", "relation": "causes" }
  ],
  "edges": [
    {
      "id": "aug_a1b2c3d4e5_E001|causes|aug_a1b2c3d4e5_VC001|1",
      "source": "aug_a1b2c3d4e5_E001",
      "target": "aug_a1b2c3d4e5_VC001",
      "predicate": "https://example.org/aieventimpact/ontology#causes",
      "predicateLabel": "causes",
      "relationCategory": "logic",
      "augmentedEdge": true,
      "weakInfluence": false,
      "edgeColor": "#F97316"
    },
    {
      "id": "aug_a1b2c3d4e5_VC001|causes|aug_a1b2c3d4e5_Out001|2",
      "source": "aug_a1b2c3d4e5_VC001",
      "target": "aug_a1b2c3d4e5_Out001",
      "predicate": "https://example.org/aieventimpact/ontology#causes",
      "predicateLabel": "causes",
      "relationCategory": "logic",
      "augmentedEdge": true,
      "weakInfluence": false,
      "edgeColor": "#F97316"
    },
    {
      "id": "aug_a1b2c3d4e5_VC001|forVariable|FederalFundsRate|3",
      "source": "aug_a1b2c3d4e5_VC001",
      "target": "FederalFundsRate",
      "predicate": "https://example.org/aieventimpact/ontology#forVariable",
      "predicateLabel": "forVariable",
      "relationCategory": "auxiliary",
      "augmentedEdge": true,
      "weakInfluence": false,
      "edgeColor": "#F97316"
    }
  ],
  "counts": {
    "nodes": 4,
    "relationships": 2,
    "edges": 3
  }
}
```

> `edges` 为展示层派生结构，因此 `counts.edges` 可能大于 `counts.relationships`。

#### 测试示例（curl）

```bash
curl "http://localhost:8080/api/augment/review/graph?runId=run_20260319_143022_123_ab3f"
```

---

### 5.4 保存审核后的图谱 JSON（高级直接编辑）

**接口说明：** 直接提交修改后的完整图谱 JSON，适合高级用户手动编辑节点和关系。图谱 JSON 格式与 `05_normalized.json` 一致（五数组结构：四类节点 + `relationships`）。

```
POST /api/augment/review/save?runId={runId}
Content-Type: application/json
```

#### 请求 Body（三种形式均支持）

**方式一：** 直接传图谱 JSON 对象（整个 body 即图谱内容）

```json
{
  "events": [...],
  "market_variables": [...],
  "variable_changes": [...],
  "valuation_outcomes": [...],
  "relationships": [...]
}
```

**方式二：** 通过 `content` 字段包装 JSON 字符串

```json
{
  "content": "{\"events\":[...],\"relationships\":[...]}"
}
```

**方式三：** 直接传 JSON 字符串（Content-Type: text/plain）

#### 提交约束

- 节点类型仅支持：`Event`、`MarketVariable`、`VariableChange`、`ValuationOutcome`
- 业务关系 `relationships[].relation` 当前仅支持：`causes`
- 若图中存在 `VariableChange` 节点，必须通过节点字段 `for_variable` 绑定对应 `MarketVariable`
- 也可通过 `forVariable` 辅助关系补充绑定，服务端会折叠进 `VariableChange.for_variable`
- 旧版本关系名（如 `causesChange`、`propagatesChange`、`affectsValuation` 等）不会被保留

#### 响应示例

```json
{ "ok": true }
```

---

### 5.5 批准审核（写入图谱）

**接口说明：** 批准当前审核结果，系统将把审核图谱转换为 TTL 文件并写入知识图谱。

> **前置条件：** 必须先调用 `paths/save` 或 `review/save` 使 `05_reviewed.json` 存在，才能批准。

```
POST /api/augment/review/approve?runId={runId}
```

#### 响应示例

```json
{ "ok": true }
```

批准成功后，可通过 `/api/augment/status` 查看完成情况：

```json
{
  "status": "COMPLETED",
  "stage": "done",
  "artifact_ttl": "06_output.ttl",
  "persistedTtl": "/data/ontology/augmented/run_20260319_143022_123_ab3f.ttl",
  "reload": { "modelSize": 1234, "elapsedMs": 320 },
  "augmentReload": { "modelSize": 1456, "elapsedMs": 280 }
}
```

> 说明：
> - 审批通过后一定会生成 `06_output.ttl`，并持久化到 `/data/ontology/augmented/<runId>.ttl`
> - 系统一定会刷新补全检索上下文（`augmentReload`）
> - 查询上下文是否立即生效取决于当前 `active` TTL 选择以及 `autoLoad` 设置，状态里的 `reload` 可能为 `null`

#### 错误码

| HTTP 状态 | 说明 |
|-----------|------|
| 400 | 审核内容未保存（`05_reviewed.json` 不存在） |
| 400 | 任务状态不是 `WAITING_REVIEW` |

#### 测试示例（curl）

```bash
curl -X POST "http://localhost:8080/api/augment/review/approve?runId=run_20260319_143022_123_ab3f"
```

---

### 5.6 拒绝审核

**接口说明：** 拒绝当前审核结果，任务状态变为 `REJECTED`。只能在 `WAITING_REVIEW` 状态时调用。

```
POST /api/augment/review/reject?runId={runId}
Content-Type: application/json
```

#### 拒绝原因传入方式（任选其一）

**方式一：** URL 参数
```
POST /api/augment/review/reject?runId=xxx&reason=补全路径有误
```

**方式二：** Body JSON
```json
{ "reason": "补全路径与实际不符，需要重新运行" }
```

**方式三：** 直接传纯文本 Body（Content-Type: text/plain）

#### 响应示例

```json
{ "ok": true }
```

---

### 5.7 获取节点候选列表

**接口说明：** 审核时可查询图谱中已有的节点，供构建自定义路径时选择节点 ID。

```
GET /api/augment/review/node-options?runId={runId}&type={type}&q={keyword}&source={source}&limit={limit}
```

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `runId` | string | 是 | - | 任务 ID |
| `type` | string | 否 | - | 节点类型过滤：`Event`、`VariableChange`、`MarketVariable`、`ValuationOutcome` |
| `q` | string | 否 | - | 关键词搜索（匹配 id 或 label，大小写不敏感） |
| `source` | string | 否 | `all` | 节点来源过滤（见下表） |
| `limit` | integer | 否 | 500 | 最多返回条数（1 ~ 20000） |

#### source 参数说明

| 值 | 含义 |
|----|------|
| `all` | 全部（基础图谱 + 已审核补全 + 本次补全） |
| `base` | 仅来自基础 TTL（`displayOrigin = base_ttl`） |
| `approved` | 仅来自已审核通过的补全 TTL（不受当前 active TTL 选择影响） |
| `editable` | 仅来自本次 LLM 补全结果（当前运行的 `05_normalized.json`） |

> 说明：若某节点同时存在于基础 TTL 与已审核 TTL，展示来源优先记为 `base_ttl`；因此 `source=approved` 主要返回仅在已审核 TTL 中新增的节点。

#### 响应示例

```json
{
  "runId": "run_20260319_143022_123_ab3f",
  "items": [
    {
      "id": "E_FedRateHike_2024",
      "label": "美联储2024年加息",
      "type": "Event",
      "direction": "",
      "for_variable": "",
      "origin": "base_ttl",
      "displayOrigin": "base_ttl",
      "isNew": false
    },
    {
      "id": "aug_a1b2c3d4e5_E001",
      "label": "美联储加息",
      "type": "Event",
      "direction": "",
      "for_variable": "",
      "origin": "editable",
      "displayOrigin": "editable",
      "isNew": true
    }
  ],
  "count": 2,
  "total": 2,
  "truncated": false,
  "filters": {
    "type": "Event",
    "q": "美联储",
    "source": "all",
    "limit": 500
  }
}
```

#### 测试示例（curl）

```bash
# 搜索 Event 类型节点，关键词"美联储"
curl "http://localhost:8080/api/augment/review/node-options?runId=run_20260319_143022_123_ab3f&type=Event&q=美联储"

# 查看所有 ValuationOutcome 节点（仅基础图谱）
curl "http://localhost:8080/api/augment/review/node-options?runId=run_20260319_143022_123_ab3f&type=ValuationOutcome&source=base"
```

---

## 六、激活 TTL 管理

**背景：** 本组接口控制的是**查询图谱（query context）**中哪些已审核通过的补全 TTL 生效。补全检索上下文（augment context）始终加载“基础 TTL + 全部已审核 TTL”，不受本组接口影响。

---

### 6.1 查看当前激活的补全 TTL

```
GET /api/augment/ttl/active
```

#### 响应示例

```json
{
  "mode": "custom",
  "activeRunIds": ["run_20260318_101500_002_cd5e"],
  "updatedAt": "2026-03-19T14:30:00Z"
}
```

#### mode 字段说明

| 值 | 含义 |
|----|------|
| `none` | 未激活任何补全 TTL |
| `custom` | 激活了指定的 runId 列表 |
| `all` | 激活全部已审核通过的 TTL。请求时可用 `["*"]` 设置该模式；响应中通过 `mode=all` 表示，`activeRunIds` 返回空数组 |

---

### 6.2 设置激活的补全 TTL

```
POST /api/augment/ttl/active
Content-Type: application/json
```

#### 请求 Body

```json
{
  "activeRunIds": ["run_20260318_101500_002_cd5e", "run_20260319_143022_123_ab3f"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `activeRunIds` | string[] | 是 | 要激活的 runId 列表；空数组 `[]` 表示不激活任何补全；请求时传 `["*"]` 表示激活全部已审核 TTL |

> **注意：** 所有传入的 runId 必须已有对应的 TTL 文件（即已审核通过），否则返回 400。
>
> 当请求传入 `["*"]` 时，响应会返回：
> ```json
> { "mode": "all", "activeRunIds": [] }
> ```

#### 响应示例

```json
{
  "mode": "custom",
  "activeRunIds": ["run_20260318_101500_002_cd5e", "run_20260319_143022_123_ab3f"],
  "updatedAt": "2026-03-19T14:35:00Z",
  "ok": true,
  "reload": { "modelSize": 1456, "elapsedMs": 280 }
}
```

---

## 七、系统设置接口

---

### 7.1 获取补全参数配置

```
GET /api/settings/augment
```

#### 响应示例

```json
{
  "extractModelId": "model/Qwen3-235b-a22b.json",
  "extractPrompt": "news_key_extract.md",
  "extractParams": {},
  "augmentModelId": "model/chatGPT5.2.json",
  "augmentPrompt": "augment_chain.md",
  "augmentParams": {},
  "similarityTopK": 5,
  "similarityThreshold": 0.6,
  "similarityUseFallbackTopForChains": false,
  "similarityAuditEnabled": true,
  "similarityAuditModelId": "model/chatGPT5.2.json",
  "similarityAuditPrompt": "similarity_audit.md",
  "includeWeakEdges": true,
  "highlightColor": "#F97316",
  "autoLoad": true
}
```

#### 主要配置字段说明

| 字段 | 说明 |
|------|------|
| `extractModelId` | 实体抽取阶段使用的模型（模型 ID 格式：`model/<文件名>.json`） |
| `augmentModelId` | 图谱补全阶段使用的模型 |
| `similarityTopK` | 相似度匹配返回的最大候选数（最小 1） |
| `similarityThreshold` | 相似度阈值（0~1，低于此值不纳入结果） |
| `similarityUseFallbackTopForChains` | 相似度无命中时是否退而使用 fallback_top 候选进行链路检索 |
| `similarityAuditEnabled` | 是否启用 LLM 对相似度结果进行二次语义复核 |
| `similarityAuditModelId` | 相似度语义复核使用的模型 |
| `includeWeakEdges` | 链路检索时是否包含弱影响边 |
| `highlightColor` | 补全节点/边在图谱中的高亮颜色（十六进制，如 `#F97316`） |
| `autoLoad` | 审核通过后是否触发查询图谱 reload。最终查询图谱是否包含当前 run，还取决于当前 active TTL 选择：`mode=all` 时会自动纳入，`custom/none` 时按 `activeRunIds` 生效 |

---

### 7.2 修改补全参数配置

```
POST /api/settings/augment
Content-Type: application/json
```

**支持部分更新**，只需传入要修改的字段，其余字段保持当前值。

```json
{
  "similarityTopK": 8,
  "similarityThreshold": 0.65,
  "autoLoad": false
}
```

#### 响应

返回更新后的完整配置（格式同 GET 响应）。

#### 测试示例（curl）

```bash
curl -X POST http://localhost:8080/api/settings/augment \
  -H "Content-Type: application/json" \
  -d '{"similarityTopK": 8, "similarityThreshold": 0.65}'
```

---

### 7.3 获取可用模型列表

```
GET /api/settings/models
```

#### 响应示例

```json
{
  "models": [
    {
      "id": "model/Qwen3-235b-a22b.json",
      "modelName": "Qwen3-235b-a22b",
      "url": "https://api.example.com/v1"
    },
    {
      "id": "model/chatGPT5.2.json",
      "modelName": "GPT-5.2",
      "url": "https://api.openai.com/v1"
    }
  ]
}
```

> `id` 字段即为配置中 `extractModelId`、`augmentModelId` 等字段应填写的值。

---

### 7.4 删除任务

```
POST /api/augment/delete?runId={runId}&force={true|false}
Content-Type: application/json
```

#### 请求参数

| 参数来源 | 参数名 | 类型 | 必填 | 默认值 | 说明 |
|---------|--------|------|------|--------|------|
| URL Query | `runId` | string | 是 | - | 任务 ID |
| URL Query | `force` | string | 否 | `false` | `true` 时可强制删除正在运行的任务 |

#### 请求 Body（可选）

```json
{
  "deleteEmbeddings": true
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `deleteEmbeddings` | boolean | `true` | 是否同时清除该任务相关的 Embedding 缓存 |

#### 响应示例

```json
{
  "ok": true,
  "runId": "run_20260319_143022_123_ab3f",
  "deletedFiles": 12,
  "ttlDeleted": false,
  "removedEmbeddings": 5
}
```

#### 错误码

| HTTP 状态 | 说明 |
|-----------|------|
| 409 | 任务正在运行，需加 `force=true` 参数 |
| 400 | 任务不存在或参数非法 |

---

## 八、完整调用流程示例

以下是一个完整的从新闻输入到图谱写入的调用流程（Shell 脚本）：

### Step 1：启动任务

```bash
RUN_ID=$(curl -s -X POST http://localhost:8080/api/augment/run \
  -H "Content-Type: application/json" \
  -d '{"newsText": "美联储宣布加息50个基点，市场普遍预期此举将抑制通胀压力，美股三大指数全线下跌。"}' \
  | jq -r .runId)

echo "任务 ID: $RUN_ID"
```

### Step 2：轮询状态

```bash
while true; do
  RESP=$(curl -s "http://localhost:8080/api/augment/status?runId=$RUN_ID")
  STATUS=$(echo $RESP | jq -r .status)
  STAGE=$(echo $RESP | jq -r .stage)
  echo "状态: $STATUS | 阶段: $STAGE"

  if [ "$STATUS" = "WAITING_REVIEW" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "COMPLETED" ]; then
    break
  fi
  sleep 5
done
```

### Step 3：查看补全结果

```bash
# 查看抽取的关键信息（含 summary、main_events、main_variable_changes、notes）
curl -s "http://localhost:8080/api/augment/artifact?runId=$RUN_ID&name=01_extract.json" | jq .

# 查看补全生成的图谱（五数组结构：四类节点 + relationships）
curl -s "http://localhost:8080/api/augment/artifact?runId=$RUN_ID&name=05_normalized.json" | jq .
```

### Step 4：查看审核路径（注意 id 字段，非 pathId）

```bash
curl -s "http://localhost:8080/api/augment/review/paths?runId=$RUN_ID" \
  | jq '.paths[] | {id, text, included, hasNew}'
```

### Step 5：选择路径并保存（includedPathIds 填写 PATH_ 开头的真实 ID）

```bash
# 先获取所有路径 ID
PATH_IDS=$(curl -s "http://localhost:8080/api/augment/review/paths?runId=$RUN_ID" \
  | jq '[.paths[] | .id]')

curl -X POST "http://localhost:8080/api/augment/review/paths/save?runId=$RUN_ID" \
  -H "Content-Type: application/json" \
  -d "{\"includedPathIds\": $PATH_IDS, \"customPaths\": []}"
```

### Step 6：批准审核写入图谱

```bash
curl -X POST "http://localhost:8080/api/augment/review/approve?runId=$RUN_ID"
```

### Step 7：（可选）让当前补全结果在查询图谱中生效

```bash
# 若当前 active 模式不是 all，且希望当前 run 立即参与查询，可手动激活
curl -X POST http://localhost:8080/api/augment/ttl/active \
  -H "Content-Type: application/json" \
  -d "{\"activeRunIds\": [\"$RUN_ID\"]}"
```

### Step 8：确认完成

```bash
curl -s "http://localhost:8080/api/augment/status?runId=$RUN_ID" \
  | jq '{status, stage, persistedTtl, reload, augmentReload}'
```

### 8.1 批量导入直通流程（不人工查看结果，直接转 TTL）

适用场景：

- 一次性导入多条新闻
- 不进入审核界面逐条查看
- 希望在任务到达 `WAITING_REVIEW` 后，直接按系统生成的 `05_normalized.json` 保存为审核结果，再批准写入 TTL

#### 推荐接口顺序（单条新闻）

> 注意：即使不人工查看结果，也不能直接调用 `review/approve`。必须先通过 `review/save` 或 `review/paths/save` 生成 `05_reviewed.json`。
>
> 对于批量直通场景，推荐使用 `review/save`，把 `05_normalized.json` 原样提交为审核结果。

1. `POST /api/augment/run`：提交新闻，拿到 `runId`
2. `GET /api/augment/status?runId=xxx`：轮询直到 `status=WAITING_REVIEW`
3. `GET /api/augment/artifact?runId=xxx&name=05_normalized.json`：获取系统标准化图谱
4. `POST /api/augment/review/save?runId=xxx`：把上一步返回的完整 JSON 原样提交
5. `POST /api/augment/review/approve?runId=xxx`：批准并转为 TTL
6. `GET /api/augment/status?runId=xxx`：确认 `status=COMPLETED`

#### 单条新闻直通示例（curl）

```bash
RUN_ID=$(curl -s -X POST http://localhost:8080/api/augment/run \
  -H "Content-Type: application/json" \
  -d '{"newsText": "美联储宣布加息50个基点，市场普遍预期此举将抑制通胀压力，美股三大指数全线下跌。"}' \
  | jq -r .runId)

while true; do
  STATUS=$(curl -s "http://localhost:8080/api/augment/status?runId=$RUN_ID" | jq -r .status)
  if [ "$STATUS" = "WAITING_REVIEW" ] || [ "$STATUS" = "FAILED" ]; then
    break
  fi
  sleep 5
done

if [ "$STATUS" = "WAITING_REVIEW" ]; then
  curl -s "http://localhost:8080/api/augment/artifact?runId=$RUN_ID&name=05_normalized.json" \
    > "/tmp/${RUN_ID}.normalized.json"

  curl -s -X POST "http://localhost:8080/api/augment/review/save?runId=$RUN_ID" \
    -H "Content-Type: application/json" \
    --data-binary "@/tmp/${RUN_ID}.normalized.json"

  curl -s -X POST "http://localhost:8080/api/augment/review/approve?runId=$RUN_ID"

  curl -s "http://localhost:8080/api/augment/status?runId=$RUN_ID" \
    | jq '{runId, status, stage, persistedTtl}'
fi
```

#### 说明

- 这套流程等价于“默认接受系统生成的完整标准化图谱”
- 如果你想走“路径全选”而不是“原样接受 `05_normalized.json`”，可改用：
  1. `GET /api/augment/review/paths`
  2. 取回全部 `paths[].id`
  3. `POST /api/augment/review/paths/save`
  4. `POST /api/augment/review/approve`
- 批量直通更建议使用 `review/save`，因为它不依赖路径枚举结果，流程更直接

---

## 九、常见问题与排查

### Q1：任务状态一直是 RUNNING 没有变化？

- 用 SSE 流接口确认是否有实时输出：
  ```bash
  curl -N "http://localhost:8080/api/augment/stream?runId=$RUN_ID" -H "Accept: text/event-stream"
  ```
- 查看是否有 `extract_done`、`similarity_audit_done`、`augment_done` 等阶段完成事件
- 查看 `04_llm_raw.txt` 产物是否已生成

### Q2：状态变为 FAILED 怎么处理？

- 查看 `/api/augment/status` 响应中的 `error` 字段
- 常见原因：

  | 错误信息 | 原因及处理 |
  |---------|-----------|
  | `未配置抽取阶段模型` | 到 `/api/settings/augment` 配置 `extractModelId` |
  | `未配置补全阶段模型` | 到 `/api/settings/augment` 配置 `augmentModelId` |
  | `模型返回内容为空` | LLM 服务异常或 Prompt 错误 |
  | `JSON 顶层必须是对象` | LLM 输出格式异常，查看 `04_llm_raw.txt` |

### Q3：paths/save 里 customPaths 怎么填？

每条自定义路径需要有 `id`（字符串，自行命名）、`nodes`（节点数组）、`relationships`（关系数组）三个字段。当前运行时：

- 业务关系只支持 `causes`
- 如果自定义路径里有 `VariableChange` 节点，必须提供 `for_variable`
- 如需补充 `VariableChange -> MarketVariable` 绑定，可在节点字段中直接写 `for_variable`，也可额外提交 `forVariable` 辅助关系
- 不能只传单个关系对象

### Q4：`includedPathIds` 里应填什么格式的 ID？

路径 ID 格式为 `PATH_` + 64位十六进制字符串（SHA256），从 `/api/augment/review/paths` 接口的 `paths[].id` 字段获取。

### Q5：批准审核后 `autoLoad=false` 图谱没有更新？

`autoLoad=false` 时审批通过后不会触发查询图谱 reload。此外，即使 `autoLoad=true`，当前 run 是否进入查询图谱仍取决于 active TTL 选择；若当前为 `mode=all` 会自动纳入，否则需手动调用：
```bash
curl -X POST http://localhost:8080/api/augment/ttl/active \
  -H "Content-Type: application/json" \
  -d "{\"activeRunIds\": [\"$RUN_ID\"]}"
```

### Q6：保存审核图时报“变量变化缺少 for_variable”怎么办？

- 说明你提交的某个 `VariableChange` 节点没有绑定对应 `MarketVariable`
- 处理方式：
  - 直接在该节点上补充 `for_variable`
  - 或在 `relationships` 中增加一条 `forVariable` 辅助关系，让系统折叠为节点绑定

### Q7：SSE 里没有 `step_done` 事件？

`step_done` 不是有效的事件名。正确的阶段完成事件格式为 `{阶段名}_done`，即：
- `extract_done`（抽取完成）
- `similarity_audit_done`（相似度复核完成）
- `augment_done`（补全完成）
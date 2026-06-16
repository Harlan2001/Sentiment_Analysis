# 宏观信号 API 接口文档

## 概述

本接口提供基于新闻文本分析的宏观信号查询能力，支持两种信号类型：

- **presence（事件存在性）**：指定时间范围内，某宏观事件是否发生（0/1）
- **directional（方向性）**：某宏观因子在指定时间范围内对国债市场的方向性影响（-1 / 0 / 1）

---

## 服务地址

| 环境 | Base URL |
|------|----------|
| 生产环境 | `http://10.253.50.112:8000` |

**Swagger 自动文档**（可在线查看所有接口与参数）：

```
http://10.253.50.112:8000/docs
```

---

## 接口

```
GET /api/macro/signal
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `factor_code` | string | ✅ | 因子代码，多个以英文逗号分隔，如 `A,B,C` |
| `start_time` | string | ✅ | 时间范围起点，ISO 格式，如 `2025-01-01T00:00:00` |
| `end_time` | string | ✅ | 时间范围终点，ISO 格式，如 `2025-01-01T23:59:59` |
| `signal_type` | string | ✅ | `presence` 或 `directional` |
| `decay_lambda` | float | ❌ | 时间衰减系数，默认 `0.1`，仅 `directional` 生效 |

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `factor_code` | string | 因子代码 |
| `signal_type` | string | 信号类型 |
| `signal_value` | int | presence: `0`/`1`；directional: `-1`/`0`/`1` |
| `confidence` | float\|null | 置信度，范围 `[0, 1]`；presence 模式固定为 `null` |
| `news_count` | int | 命中新闻数量 |
| `time_range` | object | 实际查询的时间范围 |

> 单个 `factor_code` 返回对象，多个 `factor_code` 返回数组。

---

## 因子代码一览

| factor_code | 名称 | 推荐 signal_type | 说明 |
|-------------|------|-----------------|------|
| `OPEN_MARKET_OPERATIONS` | 公开市场操作 | presence | 央行当日是否有 公开市场操作 |
| `MAJOR_MACRO_DATA_RELEASE` | 重要宏观数据发布 | presence | CPI、PMI、金融数据等官方数据发布 |
| `POLICY_GUIDANCE` | 政策表态 | presence | 央行、监管机构等官方政策表态 |
| `MONETARY_POLICY_CYCLE` | 货币政策周期 | directional | 降息/宽松为正向，加息/收紧为负向 |
| `BLACK_SWAN_SHOCK` | 黑天鹅冲击 | presence | 超预期宏观冲击事件 |
| `MACRO_REGIME_BREAK` | 宏观环境突变 | presence | 当前宏观环境发生根本性改变 |
| `POLICY_SHIFT_EVENT` | 央行政策调整 | presence | 央行政策出现方向性调整 |

---

## signal_value 含义

### presence 模式

| signal_value | 含义 |
|---|---|
| `1` | 时间范围内存在相关新闻，事件发生 |
| `0` | 时间范围内无相关新闻，事件未发生 |

### directional 模式

| signal_value | 含义 |
|---|---|
| `1` | 正向信号，利多国债（如降息预期、宽松政策） |
| `0` | 中性，无明显方向 |
| `-1` | 负向信号，利空国债（如加息预期、收紧政策） |

**方向判断逻辑**：对时间范围内所有命中新闻的方向做时间衰减加权平均，离 `end_time` 越近权重越大（$w = e^{-\lambda \cdot \Delta t}$），加权得分绝对值超过 0.3 时才判定为有方向，否则为中性。

### confidence 含义

- presence：`null`，presence 信号语义是"事件是否发生"，非此即彼，不存在置信度
- directional：归一化的衰减权重之和，命中新闻越多、时间越近，置信度越高

---

## 使用示例

### 2.1 事件验证（日频）

验证当日是否有央行操作、数据发布、政策表态等宏观驱动事件：

```http
GET http://10.253.50.112:8000/api/macro/signal
  ?factor_code=OMO_VOLUME_SIGNAL,MAJOR_MACRO_DATA_RELEASE,POLICY_GUIDANCE
  &start_time=2025-06-10T00:00:00
  &end_time=2025-06-10T23:59:59
  &signal_type=presence
```

**响应示例：**

```json
[
  {
    "factor_code": "OMO_VOLUME_SIGNAL",
    "signal_type": "presence",
    "signal_value": 1,
    "confidence": 0.6,
    "news_count": 3,
    "time_range": { "start": "2025-06-10T00:00:00", "end": "2025-06-10T23:59:59" }
  },
  {
    "factor_code": "MAJOR_MACRO_DATA_RELEASE",
    "signal_type": "presence",
    "signal_value": 0,
    "confidence": 0.0,
    "news_count": 0,
    "time_range": { "start": "2025-06-10T00:00:00", "end": "2025-06-10T23:59:59" }
  },
  {
    "factor_code": "POLICY_GUIDANCE",
    "signal_type": "presence",
    "signal_value": 1,
    "confidence": 0.4,
    "news_count": 2,
    "time_range": { "start": "2025-06-10T00:00:00", "end": "2025-06-10T23:59:59" }
  }
]
```

---

### 2.2 宏观趋势层（周频/月频）

查询当前货币政策周期方向：

```http
GET http://10.253.50.112:8000/api/macro/signal
  ?factor_code=MONETARY_POLICY_CYCLE
  &start_time=2025-05-01T00:00:00
  &end_time=2025-05-31T23:59:59
  &signal_type=directional
```

**响应示例：**

```json
{
  "factor_code": "MONETARY_POLICY_CYCLE",
  "signal_type": "directional",
  "signal_value": 1,
  "confidence": 0.87,
  "news_count": 12,
  "time_range": { "start": "2025-05-01T00:00:00", "end": "2025-05-31T23:59:59" }
}
```


---

### 2.3 事件过滤与平仓

检测是否有黑天鹅冲击或宏观环境突变：

```http
GET http://10.253.50.112:8000/api/macro/signal
  ?factor_code=BLACK_SWAN_SHOCK,MACRO_REGIME_BREAK
  &start_time=2025-06-10T00:00:00
  &end_time=2025-06-10T23:59:59
  &signal_type=presence
```

---

### 2.4 宏观事件平仓

```http
GET http://10.253.50.112:8000/api/macro/signal
  ?factor_code=POLICY_SHIFT_EVENT,MAJOR_MACRO_DATA_RELEASE
  &start_time=2025-06-10T00:00:00
  &end_time=2025-06-10T23:59:59
  &signal_type=presence
```


---

### 2.5 宏观确认与反转平仓

```http
GET http://10.253.50.112:8000/api/macro/signal
  ?factor_code=MONETARY_POLICY_CYCLE
  &start_time=2025-06-01T00:00:00
  &end_time=2025-06-10T23:59:59
  &signal_type=directional
```


---

## 错误码

| HTTP 状态码 | 原因 |
|---|---|
| `400` | 参数格式错误（时间格式非 ISO、`signal_type` 不合法、`factor_code` 为空） |
| `500` | 服务内部错误 |

当某个 `factor_code` 在数据库中不存在时，该条目返回：

```json
{ "factor_code": "UNKNOWN_CODE", "error": "not found" }
```

---

## 注意事项

1. **时间范围建议**：日频策略使用当日 `00:00:00` ~ `23:59:59`；周频/月频策略按自然周/月设置范围
2. **presence 与 directional 区别**：事件类因子（是否发生）用 presence；趋势类因子（方向是什么）用 directional
4. **时间衰减参数**：`decay_lambda` 默认 0.1，即距 `end_time` 约 7 天后权重衰减至 50%；若希望更侧重近期新闻可适当调大，如 0.3

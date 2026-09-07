# 组合策略分析 — 接口说明

## 接口

- **方式**：`POST`
- **路径**：`/sapi/strategy/portfolio-analysis`
- **地址示例**：`http://<host>:8000/sapi/strategy/portfolio-analysis`（路由统一挂在 `API_PREFIX`，默认 `/sapi`）
- **鉴权**：当前无（与 `AUTH_ENABLED` 默认关闭一致）

## 请求

```json
{
  "force_refresh": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `force_refresh` | boolean | 否 | 是否跳过缓存重新分析，默认 `false` |

### 调用示例

```bash
# 普通请求（优先命中缓存）
curl -X POST "http://<host>:8000/sapi/strategy/portfolio-analysis" \
  -H "Content-Type: application/json" \
  -d "{}"

# 强制刷新
curl -X POST "http://<host>:8000/sapi/strategy/portfolio-analysis" \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'
```

```javascript
const res = await fetch('http://<host>:8000/sapi/strategy/portfolio-analysis', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ force_refresh: false })
});
const json = await res.json();
// json.data.analysis → 分析结果
// json.data.meta     → 元信息
```

## 成功响应（200）

响应壳遵循项目统一约定 `{"data": <payload>}`（见 `backend/common/api_response.py` 的 `ok()`）。

```json
{
  "data": {
    "analysis": {
      "general": {
        "duration_years": { "min": 1.5, "max": 3.0 },
        "single_bond_weight_pct": { "min": 2.0, "max": 8.0 },
        "min_rating": "AA+",
        "portfolio_fund_wan": 100.0
      },
      "distribution_by_category": {
        "gov_bond": { "min": 10.0, "max": 30.0 },
        "local_gov_bond": { "min": 5.0, "max": 20.0 },
        "corp_credit_bond": { "min": 10.0, "max": 30.0 },
        "financial_bond_non_policy": { "min": 5.0, "max": 20.0 },
        "other_bond": { "min": 0.0, "max": 10.0 },
        "policy_financial_bond": { "min": 5.0, "max": 20.0 },
        "gov_supported_institution_bond": { "min": 0.0, "max": 15.0 },
        "cd": { "min": 0.0, "max": 10.0 },
        "abs": { "min": 0.0, "max": 10.0 }
      },
      "distribution_by_type": {
        "interest_rate_bond": { "min": 30.0, "max": 60.0 },
        "credit_bond": { "min": 40.0, "max": 70.0 }
      }
    },
    "meta": {
      "cache_hit": false,
      "request_id": "uuid",
      "model_name": "glm",
      "news_count": 50,
      "window_start": "2026-06-27 00:00:00",
      "window_end": "2026-06-28 00:00:00",
      "latest_news_pub_time": "2026-06-27 18:30:00",
      "latency_ms": 3500
    }
  }
}
```

### 目标新闻日

默认目标新闻日 = **北京时间今天之前最近一个有新闻的日期**：

- 普通工作日即昨天；
- 周一/节假日自动取上一交易日，避免非交易日落空；
- 分析窗口为该日 `00:00:00 ~ 次日 00:00:00`，参与分析的新闻为该日 `reason` 非空的 AI 研判（每条取最高优先级模型，最多 50 条）。

### data.analysis.general

| 字段 | 类型 | 说明 |
|------|------|------|
| `duration_years` | `{min, max}` | 组合久期区间（年） |
| `single_bond_weight_pct` | `{min, max}` | 单券权重区间（%） |
| `min_rating` | string | 最低评级，枚举：`不限` `AAA` `AA+` `AA` `AA-` `A+` `A` `A-` `BBB+` |
| `portfolio_fund_wan` | number | 组合资金（万元） |

### data.analysis.distribution_by_category

| 字段 | 含义 |
|------|------|
| `gov_bond` | 国债 |
| `local_gov_bond` | 地方政府债 |
| `corp_credit_bond` | 公司信用债 |
| `financial_bond_non_policy` | 金融债(不含政策性) |
| `other_bond` | 其它债券 |
| `policy_financial_bond` | 政策性金融债 |
| `gov_supported_institution_bond` | 政府支持机构债 |
| `cd` | 同业存单 |
| `abs` | 资产支持证券 |

### data.analysis.distribution_by_type

| 字段 | 含义 |
|------|------|
| `interest_rate_bond` | 利率债 |
| `credit_bond` | 信用债 |

### 校验规则

- 单区间：每个 `{min, max}` 满足 `0 ≤ min ≤ max`（`duration_years` 单位为年，其余为 %）。
- 总和（与 `docs/组合策略字段说明.md` 规则 3 一致）：`distribution_by_category` 与 `distribution_by_type` 两组各自满足 **所有 min 之和 ≤ 100** 且 **所有 max 之和 ≥ 100**，保证区间组合可达。
- 不满足以上任一规则视为「模型输出不满足校验规则」，接口返回 500。

### data.meta

| 字段 | 说明 |
|------|------|
| `cache_hit` | 是否命中缓存 |
| `request_id` | 请求唯一 ID（排查用） |
| `model_name` | 使用的分析模型短名（当前注册表：`glm` / `deepseek` / `qwen` / `kimi`，缺省跟随 `ANALYSIS_MODEL_NAME`） |
| `news_count` | 参与分析的新闻条数 |
| `window_start/end` | 分析时间窗口 |
| `latest_news_pub_time` | 最新新闻发布时间 |
| `latency_ms` | 处理耗时（毫秒） |

## 失败响应（500）

```json
{
  "detail": "组合策略分析失败: 目标新闻日没有可分析的新闻或 reason 数据为空"
}
```

常见失败原因：
- 无任何可用新闻（新闻表为空）
- 目标新闻日没有 `reason` 非空的分析结果
- 模型输出非 JSON 或不满足校验规则（键缺失、`min > max`、`min_rating` 越界等）
- LLM 网关不可达或超时

## 缓存说明

结果写入 `portfolio_strategy_analysis_cache` 表，`cache_key` 格式：

```
portfolio-analysis:{目标新闻日期}:{模型短名}:{数据版本}
```

（数据版本随输出契约/prompt 调整递增，使旧缓存自然失效。）同一 `cache_key` 命中成功缓存后直接返回，不重复调用 LLM；传 `force_refresh=true` 强制重算并覆盖。失败仅记录 `status='fail'` 与错误信息，不当作成功缓存返回。
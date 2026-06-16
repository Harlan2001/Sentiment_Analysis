# analyzer_runner 修改后操作指南

本文档说明修改后的新闻分析执行器如何配置和运行：
- 入口模块：backend.analysis.analyzer_runner
- 运行方式：建议使用 Python 模块方式启动
- 配置方式：自动从项目根目录 .env 读取环境变量

## 1. 变更点与影响

当前版本在执行器文件顶部增加了 dotenv 加载逻辑，会自动读取项目根目录的 .env：

- 文件内逻辑：load_dotenv(Path(__file__).parent.parent.parent / ".env")
- 影响：运行前不需要手工 export 环境变量（前提是 .env 配置完整）

## 2. 运行前准备

### 2.1 进入项目根目录

请在 Sentiment 根目录执行命令。

### 2.2 激活 Python 环境（Windows + Conda）

```powershell
conda activate sentiment
```

如果环境名不是 sentiment，请替换为你的实际环境名。

### 2.3 安装依赖

```powershell
pip install -r requirements.txt
```

## 3. 环境变量配置

### 3.1 生成 .env

项目已提供 .env.example，先复制：

```powershell
Copy-Item .env.example .env
```

### 3.2 必填项

请至少配置以下字段：

```env
kingstar_API_KEY=你的API密钥
kingstar_BASE_URL=你的OpenAI兼容网关地址

MYSQL_HOST=你的MySQL地址
MYSQL_PORT=3306
MYSQL_USER=你的MySQL用户名
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=Sentiment_analysis
MYSQL_CHARSET=utf8mb4
MYSQL_AUTOCOMMIT=true
```

### 3.3 可选项

```env
ANALYSIS_MODEL_NAME=doubao
PYTHONUNBUFFERED=1
```

说明：
- ANALYSIS_MODEL_NAME 默认是 doubao，可改为 deepseek 或 qwen（需在注册表中已启用）。
- kingstar_BASE_URL 需要指向 OpenAI 兼容接口网关，而不是本项目 FastAPI 的 /api/chat。

## 4. 命令行参数说明

执行器命令支持以下参数：

- --max-concurrent：最大并发数，默认 20
- --batch-size：每批处理数量，默认 100
- --limit：本次最大处理数量，默认 1000
- --mode：执行模式，支持 model_missing / force_rerun
- --start-time：起始时间，格式 YYYY-MM-DD HH:MM:SS
- --end-time：结束时间，格式 YYYY-MM-DD HH:MM:SS
- --news-ids：指定新闻 ID 列表，逗号分隔

## 5. 推荐运行命令

### 5.1 常规补分析（推荐）

仅处理“该模型尚无结果”的新闻。

```powershell
python -m backend.analysis.analyzer_runner --mode model_missing --batch-size 100 --max-concurrent 5 --limit 10000
```

### 5.2 强制重跑（谨慎）

会按筛选条件重新跑，适合模型升级后的回补。

```powershell
python -m backend.analysis.analyzer_runner --mode force_rerun --batch-size 100 --max-concurrent 20 --limit 10000
```

### 5.3 指定时间窗口

```powershell
python -m backend.analysis.analyzer_runner --mode model_missing --start-time "2026-05-01 00:00:00" --end-time "2026-05-09 23:59:59" --batch-size 100 --max-concurrent 20 --limit 5000
```

### 5.4 指定新闻 ID 精确重跑

```powershell
python -m backend.analysis.analyzer_runner --mode force_rerun --news-ids "1001,1002,1003" --batch-size 20 --max-concurrent 5 --limit 100
```

## 6. 两种 mode 选择建议

- model_missing：优先用于日常补分析，避免重复处理。
- force_rerun：用于模型切换、策略修复后的历史回放。

补充说明：
- 即使 force_rerun，单条处理时仍有“已存在同模型结果则跳过”的保护逻辑；是否被选中由前置筛选决定。

## 7. 输出与排查

### 7.1 运行统计

任务结束会输出：
- 总新闻数
- 已处理数
- 成功数
- 失败数
- 跳过数
- 总耗时与处理速度

### 7.2 失败明细文件

每次运行会自动写入：

- 目录：logs/analysis_issues
- 文件名：analysis_issues_YYYYMMDD_HHMMSS.json

文件包含 failed 和 skipped 的详细原因，可直接用于排查。

### 7.3 常见错误

1) kingstar_API_KEY 未设置
- 现象：启动时报 ValueError
- 处理：检查 .env 中 kingstar_API_KEY 是否存在，是否在项目根目录

2) kingstar_BASE_URL 配置错误
- 现象：OpenAI 调用 404 或路由不匹配
- 处理：确认 BASE_URL 指向 OpenAI 兼容网关，不是本项目 /api/chat

3) MySQL 连接失败
- 现象：pymysql 连接异常或超时
- 处理：检查 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE 是否正确，并确认网络可达

4) 因子读取失败
- 现象：启动后因子加载报错
- 处理：确认数据库 factor 表存在且可读

## 8. 最小可执行示例（建议先跑）

```powershell
python -m backend.analysis.analyzer_runner --mode model_missing --batch-size 20 --max-concurrent 5 --limit 200
```

先小流量验证，再逐步把 batch-size / max-concurrent 提高到生产值。

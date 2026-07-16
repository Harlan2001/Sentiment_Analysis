# Docker 部署指南

> 前端 Nginx + 后端 FastAPI 双容器部署。**代码通过 volume 挂载，日常更新只传文件不重打镜像。**

## 1. 部署架构

```
┌─────────────────┐     ┌─────────────────┐
│   frontend      │────►│   backend       │
│   Nginx :80     │     │   FastAPI :8000 │
│                 │     │                 │
│                 │     │ main.py ←volume │
│        (不挂载)  │     │ backend/←volume │
└─────────────────┘     └────────┬────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │ ./data          │ ./logs           │ ./models
               │ (持久化)         │ (持久化)         │ (只读)
               └─────────────────┴──────────────────┘
```

- 前端 Nginx 负责静态资源和 `/api/*`、`/health` 反向代理
- 后端代码通过 `:ro` 只读 volume 挂载，更新代码 = scp 文件 + restart
- 前端不挂 volume，变动较少时走镜像重建

## 2. 部署目标

| 名称 | 地址 | 用户 | 密码 | 路径 | 连接方式 |
|------|------|------|------|------|----------|
| **大前台** | `10.253.50.112` | `admin` | `Kingstar2022!` | `/opt/sentiment` | 直连 SSH |
| **Saas** | `172.18.0.23` | `root` | `Kayak2020!` | `/data/sentiment` | 跳板机 → 见下文 |

**Saas 跳板机**：
- 地址：`114.67.114.200`，端口 `2222`
- 用户：`root`，密码：`Kayak2020!`
- SSH 命令示例：`ssh -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" root@172.18.0.23`

## 3. 运行要求

- Docker 20.10+
- Docker Compose v2+
- 至少 8GB 内存，推荐 16GB
- 至少 20GB 可用磁盘空间
- 外部 MySQL 5.7+ 数据库

## 4. 环境变量

服务器上 `.env` 文件（与 `docker-compose.yml` 同目录）：

```env
kingstar_API_KEY=sk-xxx
kingstar_BASE_URL=https://api.kingstarinfotech.cn/dmx/openai/v1
MYSQL_HOST=10.253.50.134
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=Sentiment_analysis
MYSQL_CHARSET=utf8mb4
MYSQL_AUTOCOMMIT=true
PYTHONUNBUFFERED=1
```

## 5. 三种部署模式

### 模式 A：后端代码更新（依赖未变，最常见）

后端代码变了但 `pyproject.toml` / `uv.lock` 没变时，**只传代码文件**，不重打镜像：

```bash
# 大前台
./scripts/deploy.sh bigfrontend

# Saas
./scripts/deploy.sh saas

# 双服务器
./scripts/deploy.sh both
```

脚本做的事：
1. rsync/scp `main.py` + `backend/` 到服务器
2. 传输 `deploy/*.sh` 定时任务脚本
3. `docker compose restart backend`

### 模式 B：前端更新（构建机 build → 传镜像 → 服务器 load）

前端源码变更时，**只重建前端镜像**，后端不动：

```bash
# === 1. 本地构建（WSL / 开发机）===
cd /path/to/sentiment
docker compose build --no-cache frontend

# === 2. 导出并传输 ===
docker save sentiment-frontend:latest | gzip > sentiment-frontend.tar.gz

# 大前台
scp sentiment-frontend.tar.gz admin@10.253.50.112:/opt/sentiment/

# Saas（经跳板机）
scp -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" \
    sentiment-frontend.tar.gz root@172.18.0.23:/data/sentiment/

# === 3. 服务器加载镜像并重启 ===
ssh admin@10.253.50.112
cd /opt/sentiment
gunzip -c sentiment-frontend.tar.gz | docker load   # ← 这一步容易忘！
docker compose up -d frontend
```

关键三步不能漏：**build → save & scp → gunzip -c | docker load → up -d**。

> **注意**：前端没有 volume 挂载，任何时候改前端源码都要走这个流程。后端 `pyproject.toml` / `uv.lock` 没变就别 rebuild 后端镜像，省时间。

### 模式 C：完整镜像重建（依赖变更 / 大版本）

`pyproject.toml` / `uv.lock` 或前端 `package*.json` 变更时，重打两个镜像：

```bash
# 大前台
./scripts/deploy-image.sh bigfrontend

# Saas
./scripts/deploy-image.sh saas

# 双服务器
./scripts/deploy-image.sh both
```

脚本做的事：
1. 本地 `docker compose build --no-cache`
2. `docker save` → gzip → scp 到服务器
3. 传输 `deploy/*.sh` 定时任务脚本
4. 服务器 `gunzip -c | docker load` → `docker compose up -d --force-recreate`

> **注意**：前端镜像构建必须加 `--no-cache`。Docker 层缓存有时检测不到 `COPY . .` 的文件变化（尤其在 WSL / 跨文件系统场景），导致构建出的 JS bundle 仍是旧代码。

## 6. 目录结构

### 构建机（你的开发机）

```
.
├── docker-compose.yml       # 编排文件
├── Dockerfile               # 后端镜像
├── pyproject.toml           # Python 项目配置
├── uv.lock                  # 依赖锁定文件
├── main.py
├── backend/
├── frontend/
│   ├── Dockerfile           # 前端镜像
│   ├── nginx.conf
│   └── src/                 # 前端源码
├── scripts/
│   ├── deploy.sh            # 快速部署
│   └── deploy-image.sh      # 镜像重建部署
└── deploy/
    ├── yield_update.sh      # Cron: 收益率更新
    ├── report_gen.sh        # Cron: 报告生成
    └── analysis_fallback.sh # Cron: 分析兜底
```

### 服务器

```
/opt/sentiment/          ← 大前台
/data/sentiment/         ← Saas
├── docker-compose.yml
├── .env                        # 生产环境变量
├── main.py                     ← volume 挂载
├── backend/                    ← volume 挂载
├── data/                       ← 数据持久化
├── logs/                       ← 日志
├── models/                     ← ML 模型
├── sentiment-backend.tar.gz    ← 传输的镜像文件
├── sentiment-frontend.tar.gz
├── yield_update.sh
├── report_gen.sh
└── analysis_fallback.sh
```

## 7. 首次部署

### 7.1 构建镜像

```bash
cd /path/to/sentiment
docker compose build --no-cache
```

### 7.2 传输镜像 + 代码到服务器

```bash
# 镜像
docker save sentiment-backend:latest | gzip > sentiment-backend.tar.gz
docker save sentiment-frontend:latest | gzip > sentiment-frontend.tar.gz

# === 大前台 ===
scp sentiment-backend.tar.gz sentiment-frontend.tar.gz admin@10.253.50.112:/opt/sentiment/
scp docker-compose.yml admin@10.253.50.112:/opt/sentiment/
scp -r main.py backend/ admin@10.253.50.112:/opt/sentiment/

# === Saas（经跳板机）===
scp -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" \
    sentiment-backend.tar.gz sentiment-frontend.tar.gz root@172.18.0.23:/data/sentiment/
# ... 同理传 docker-compose.yml、代码等
```

### 7.3 服务器加载镜像并启动

```bash
# 大前台
ssh admin@10.253.50.112
cd /opt/sentiment
gunzip -c sentiment-backend.tar.gz | docker load
gunzip -c sentiment-frontend.tar.gz | docker load
docker compose up -d --force-recreate

# Saas（经跳板机）
ssh -o "ProxyCommand=ssh -p 2222 root@114.67.114.200 -W %h:%p" root@172.18.0.23
cd /data/sentiment
gunzip -c sentiment-backend.tar.gz | docker load
gunzip -c sentiment-frontend.tar.gz | docker load
docker compose up -d --force-recreate
```

### 7.4 验证

```bash
docker compose ps
docker compose logs -f backend
curl http://localhost:8000/health
```

## 8. 定时任务

服务器上的 Cron 配置（`crontab -e`）：

```
# 每天 19:00 — 收益率数据更新
0 19 * * * /opt/sentiment/yield_update.sh

# 每天 09:00 — 生成昨日交易日报告
0 9 * * * /opt/sentiment/report_gen.sh

# 每天 23:00 — 分析补偿兜底
0 23 * * * /opt/sentiment/analysis_fallback.sh
```

## 9. 日常运维

### 查看日志

```bash
docker compose logs -f
docker compose logs --tail=100 backend
```

### 重启服务

```bash
docker compose restart            # 快速重启
docker compose up -d --force-recreate  # 完全重建
```

### 停止服务

```bash
docker compose stop
docker compose down
```

### 进入容器

```bash
docker compose exec backend bash
```

### 备份数据

```bash
mkdir -p backups
tar -czf backups/sentiment-data-$(date +%Y%m%d).tar.gz data/ logs/ models/
tar -czf backups/sentiment-config-$(date +%Y%m%d).tar.gz docker-compose.yml .env
```

### 清理磁盘

```bash
docker image prune -f     # 清理无标签镜像
docker system prune -f    # 全面清理
```

## 10. 快速参考

| 场景 | 命令 |
|------|------|
| 后端代码更新（大前台） | `./scripts/deploy.sh bigfrontend` |
| 后端代码更新（Saas） | `./scripts/deploy.sh saas` |
| 后端代码更新（双服务器） | `./scripts/deploy.sh both` |
| 前端更新 | 看模式 B：build → save & scp → gunzip \| docker load → up -d |
| 完整镜像重建（大前台） | `./scripts/deploy-image.sh bigfrontend` |
| 完整镜像重建（Saas） | `./scripts/deploy-image.sh saas` |
| 完整镜像重建（双服务器） | `./scripts/deploy-image.sh both` |
| 首次部署 | 见第 7 节 |
# Docker 部署指南

> 前端 Nginx + 后端 FastAPI 双容器部署。后端代码通过 volume 挂载，日常更新只传文件不重打镜像；依赖或运行环境变化时，在构建机生成后端镜像并上传到服务器。服务器无需访问镜像仓库或互联网。

## 1. 部署架构

```
┌─────────────────┐     ┌─────────────────┐
│   frontend      │────►│   backend       │
│   Nginx :80     │     │   FastAPI :8000 │
│                 │     │                 │
│        (不挂载)  │     │ main.py ←volume │
│                 │     │ backend/←volume │
└─────────────────┘     └────────┬────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │ ./data          │ ./logs           │ ./models
               │ (持久化)         │ (持久化)         │ (只读)
               └─────────────────┴──────────────────┘
```

- 前端 Nginx 负责静态资源和 `/api/*`、`/health` 反向代理
- 后端代码通过 `:ro` 只读 volume 挂载，更新代码 = 传文件 + restart
- 前端不挂 volume，变动时走镜像重建

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

环境变量分两层管理：

- **`release/{target}.env`**（构建机）— 各目标服务器的完整配置，部署时自动复制到服务器并重命名为 `.env`
- **服务器 `.env`** — `docker-compose.yml` 同级目录，Docker Compose 自动加载

`release/bigfrontend.env` / `release/saas.env` 示例（完整列表见 `docker-compose.yml`）：

```env
# ===== Kingstar LLM API =====
LLM_API_KEY=sk-xxx
LLM_BASE_URL=http://api-inner.kingstarinfotech.cn/dmx/openai/v1

# ===== MySQL 数据库 =====
MYSQL_HOST=10.253.50.134
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=Sentiment_analysis
MYSQL_CHARSET=utf8mb4
MYSQL_AUTOCOMMIT=true

# ===== 分析模型 =====
ANALYSIS_MODEL_NAME=glm
CHAT_MODEL_NAME=glm

# ===== 网络代理 =====
OUTBOUND_PROXY_ENABLED=true
HTTP_PROXY=http://172.18.0.11:8889
HTTPS_PROXY=http://172.18.0.11:8889

# ===== 运行时 =====
PYTHONUNBUFFERED=1
```

> **注意**：`HTTP_PROXY` / `HTTPS_PROXY` 是操作系统级环境变量，httpx 和 requests 库会自动读取。如果 `OUTBOUND_PROXY_ENABLED=false` 但容器内仍设置了这两个变量，OpenAI SDK 仍会走代理。确保两边同步关闭或通过 `proxy={}` 在代码层防御（已修复）。

## 5. 三种部署模式

### 模式 A：后端代码更新（依赖未变，最常见）

后端代码变了但 `pyproject.toml` / `uv.lock` 没变时，**只传代码文件**，不重打镜像：

```bash
# 大前台
./scripts/deploy_backend_code.sh bigfrontend

# Saas
./scripts/deploy_backend_code.sh saas

# 双服务器
./scripts/deploy_backend_code.sh both
```

脚本做的事：
1. 打包 `main.py` + `backend/` + `docker-compose.yml` + `release/{target}.env` + 定时任务脚本
2. scp 到服务器并解包
3. 执行 `docker compose up -d backend`。该命令不强制重建容器；若服务未自动重载代码，需额外执行 `docker compose restart backend`

### 模式 B：前端更新（构建机 build → 传镜像 → 服务器 load）

前端源码变更时，**只重建前端镜像**，后端不动：

```bash
# 大前台
./scripts/deploy_frontend.sh bigfrontend

# Saas
./scripts/deploy_frontend.sh saas

# 双服务器
./scripts/deploy_frontend.sh both
```

脚本做的事：
1. `docker compose build --no-cache frontend`
2. `docker save → gzip → scp` 到服务器
3. 服务器 `gunzip -c | docker load` → `docker compose up -d frontend`

> **注意**：前端镜像构建必须加 `--no-cache`。Docker 层缓存有时检测不到 `COPY . .` 的文件变化（尤其在 WSL / 跨文件系统场景），导致构建出的 JS bundle 仍是旧代码。

### 模式 C：后端镜像发布（依赖或运行环境变更）

`pyproject.toml`、`uv.lock`、`Dockerfile` 或系统运行依赖变更时，在**构建机**重建后端镜像，再发布到服务器。前端镜像和前端容器不会被操作：

```bash
# 大前台
./scripts/deploy-backend-image.sh bigfrontend

# Saas
./scripts/deploy-backend-image.sh saas

# 双服务器
./scripts/deploy-backend-image.sh both
```

脚本做的事：
1. 构建机执行 `docker compose build backend`
2. 构建机执行 `docker save sentiment-backend:latest | gzip`，再通过 `scp` 上传镜像包
3. 传输 `release/{target}.env` + `docker-compose.yml` + 定时任务脚本
4. 服务器执行 `gunzip -c | docker load`，随后执行 `docker compose up -d --no-deps --force-recreate backend`

服务器端不会执行 `docker build`、`docker pull` 或前端构建；只需能通过 SSH/SCP 接收文件，并已安装 Docker 和 Docker Compose。

> **代码挂载说明**：当前 compose 将服务器的 `main.py` 和 `backend/` 挂载进容器。因此 Python 业务代码通常应使用模式 A 发布；模式 C 用于更新镜像中的依赖和运行环境。镜像中的同名代码会被这两个挂载覆盖。


## 7. 首次部署

### 7.1 构建镜像

```bash
cd /path/to/sentiment
docker compose build --no-cache
```

### 7.2 导出并传输镜像

```bash
docker save sentiment-backend:latest | gzip > sentiment-backend.tar.gz
docker save sentiment-frontend:latest | gzip > sentiment-frontend.tar.gz
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

# 每天 09:00 — 生成并推送报告
0 9 * * * /opt/sentiment/report_push.sh

# 每天 23:00 — 分析补偿兜底
0 23 * * * /opt/sentiment/analysis_fallback.sh
```

脚本文件在构建机 `scripts/deploy/` 目录，按服务器区分后缀（`_bigfrontend.sh` / `_saas.sh`），部署时自动去掉后缀复制到服务器。**不同服务器的 Cron 内容完全一样**，因为脚本名已统一。

## 9. 日常运维

### 查看日志

```bash
docker compose logs -f
docker compose logs --tail=100 backend
```

### 重启服务

```bash
docker compose restart                     # 快速重启
docker compose up -d --force-recreate      # 完全重建
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

### 清理磁盘

```bash
docker image prune -f     # 清理无标签镜像
docker system prune -f    # 全面清理
```

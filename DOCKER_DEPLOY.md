# Docker 部署指南

> 本文档只适用于当前的 sentiment-big-frontend 版本。它描述的是前端 Nginx + 后端 FastAPI 的双容器部署方式，不再沿用基础版的单体部署或旧脚本流程。

## 1. 部署结构

当前仓库里和部署相关的文件如下：

```text
.
├── Dockerfile              # 后端镜像
├── docker-compose.yml      # 根目录编排文件
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── frontend/
│   ├── Dockerfile          # 前端镜像
│   └── nginx.conf          # 前端 Nginx 配置
└── deploy/                 # 离线部署副本目录
    ├── Dockerfile
    ├── docker-compose.yml
    ├── .env.example
    └── frontend/
```

部署时，前端容器对外暴露 80 端口，后端容器对外暴露 8000 端口。前端 Nginx 负责静态资源和 `/api/*`、`/health` 反向代理。

## 2. 运行要求

- Docker 20.10+
- Docker Compose v2+
- Linux x86_64 服务器，建议 CentOS 7 / Ubuntu 18.04 及以上
- 至少 8GB 内存，推荐 16GB
- 至少 20GB 可用磁盘空间
- 外部 MySQL 5.7+ 数据库，项目不内置 MySQL 容器

## 3. 环境变量

先复制模板文件：

```bash
cp .env.example .env
```

当前版本至少需要配置这些项：

```env
kingstar_API_KEY=你的实际密钥
kingstar_BASE_URL=你的OpenAI兼容网关地址

MYSQL_HOST=你的MySQL地址
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=Sentiment_analysis
MYSQL_CHARSET=utf8mb4

PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

说明：

- `kingstar_API_KEY` 必填
- `kingstar_BASE_URL` 必填
- `MYSQL_PASSWORD` 必填
- 其余字段可按需覆盖

## 5. 离线部署

如果服务器不能联网，在有网络的机器上先构建镜像，再把镜像和部署文件传到服务器。

### 5.1 在构建机器上打包

```bash
cd /path/to/sentiment-big-frontend
cp .env.example .env
vim .env

docker compose build --no-cache
docker save sentiment-backend-big-frontend:latest | gzip > sentiment-backend-big-frontend.tar.gz
docker save sentiment-frontend-big-frontend:latest | gzip > sentiment-frontend-big-frontend.tar.gz
```

如果 `data`、`logs`、`models` 有新增内容，也一并同步。

### 5.2 传到服务器

```bash
scp sentiment-backend-big-frontend.tar.gz sentiment-frontend-big-frontend.tar.gz admin@10.253.50.112:/opt/sentiment/deploy/
scp -r docker-compose.yml Dockerfile .env.example frontend admin@10.253.50.112:/opt/sentiment/deploy/
scp -r data logs models admin@10.253.50.112:/opt/sentiment/
```

### 5.3 在服务器上加载镜像并启动

```bash
cd /opt/sentiment/deploy
gunzip -c sentiment-backend-big-frontend.tar.gz | docker load
gunzip -c sentiment-frontend-big-frontend.tar.gz | docker load

docker compose up -d --force-recreate
docker compose ps
docker compose logs -f
```

## 6. 日常运维

### 查看日志

```bash
docker compose logs -f
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs --tail=100 backend
```

### 重启服务

```bash
docker compose restart
docker compose restart backend
docker compose restart frontend
docker compose up -d --force-recreate
```

### 停止服务

```bash
docker compose stop
docker compose down
```

### 查看资源和进入容器

```bash
docker stats
docker compose exec backend bash
docker compose exec frontend sh
```

### 备份数据

```bash
mkdir -p backups
tar -czf backups/sentiment-data-$(date +%Y%m%d).tar.gz data/ logs/ models/
tar -czf backups/sentiment-config-$(date +%Y%m%d).tar.gz docker-compose.yml .env frontend/nginx.conf
```

## 7. 版本更新

代码更新后，执行下面步骤：

```bash
cd /opt/sentiment
git pull
docker compose build --no-cache
docker compose up -d --force-recreate
docker compose ps
docker compose logs -f backend
```

如果只改了配置，通常只需要更新 `.env` 后执行：

```bash
docker compose up -d --force-recreate
```

## 8. 故障排查

### 容器无法启动

```bash
docker compose logs backend
docker compose config | grep kingstar_API_KEY
docker compose restart backend
```

### 健康检查失败

```bash
curl http://127.0.0.1:8000/health
docker compose logs backend --since 1h
```

### 前端无法访问后端 API

```bash
docker compose logs frontend
docker compose exec frontend cat /etc/nginx/conf.d/default.conf
```

### 数据库连接失败

```bash
docker compose exec backend bash
python -c "from backend.config import MYSQL_CONFIG; print(MYSQL_CONFIG)"
```

## 9. 检查清单

- [ ] `docker compose ps` 显示两个服务都已启动
- [ ] `curl http://localhost:8000/health` 返回正常
- [ ] `curl http://localhost/` 能返回前端页面
- [ ] `/api/news` 能正常返回数据
- [ ] `.env` 已配置 `kingstar_API_KEY`、`kingstar_BASE_URL` 和 MySQL 信息
- [ ] `data/`、`logs/`、`models/` 目录已准备好

## 10. 补充说明

当前仓库保留了根目录和 `deploy/` 两套部署副本，内容都属于当前版本的部署材料。若后续需要定时任务，请在宿主机侧单独编排，不要再沿用基础版里的旧脚本流程。

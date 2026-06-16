# 阶段1: 构建前端
FROM node:20-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
    
WORKDIR /app

# 复制 package 文件
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 阶段2: Nginx 镜像
FROM nginx:alpine

# 安装 nc (netcat)
RUN apk add --no-cache netcat-openbsd

# 复制构建产物到 Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD nc -z localhost 80 || exit 1

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]

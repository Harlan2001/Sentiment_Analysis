# Sentiment Analysis（事件信号 / 舆情预测）

本项目包含 **FastAPI 后端** + **Vite 前端**，用于事件舆情分析与情绪预测。

---

## 项目结构

```text
.
├── main.py                 # FastAPI 入口（main:app）
├── requirements.txt        # Python 依赖
├── start.ps1               # Windows 本地开发启动脚本
├── start.sh                # Linux 服务器启动脚本
├── frontend/               # 前端（Vite）
│   ├── package.json
│   └── ...
└── README.md
```

---

## 运行环境要求

### 通用

- Git

### 后端

- Python 3.11
- Conda（推荐）或 venv

### 前端

- Node.js 18+
- npm

---

## 一、Windows 本地开发（开发模式）

> 适合功能开发与调试

### 1. 创建并激活 Conda 环境

```powershell
conda create -n Sentiment python=3.11
conda activate Sentiment
```

### 2. 安装后端依赖

```powershell
pip install -r requirements.txt
```

### 3. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

### 4. 启动

```powershell
.\start.ps1
```

启动后：

- 前端：[http://localhost:5173](http://localhost:5173)
- 后端：[http://127.0.0.1:8000](http://127.0.0.1:8000)

## 连接服务器

ssh admin@10.253.50.112
Kingstar2022!

## 系统

http://10.253.162.113:1080/ui/portal/#/login
admin  
Qwer!@#$124

## mysql
db_config = {
    'url': 'jdbc:mysql://10.253.50.134:3306/quotation?allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=Asia/Shanghai',
    'username': 'root',
    'password': '123456',
    'driver-class-name': 'com.mysql.cj.jdbc.Driver'
}

数据库名称：Sentiment_analysis

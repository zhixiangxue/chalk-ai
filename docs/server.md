# Chalk 服务器启动指南

本文档说明如何启动Chalk服务器。

## 前置要求

- Python 3.8+
- Redis服务器

## 启动步骤

### 1. 安装依赖

在项目根目录的虚拟环境中安装依赖：

```bash
# 激活虚拟环境
.\.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动Redis

Chalk依赖Redis进行消息队列和数据存储。

**Windows:**
```bash
redis-server
```

**Linux/Mac:**
```bash
# 使用默认配置启动
redis-server

# 或后台运行
redis-server --daemonize yes
```

**验证Redis运行:**
```bash
redis-cli ping
# 应该返回: PONG
```

### 3. 配置环境变量（可选）

复制环境变量配置模板：

```bash
cp .env.example .env
```

修改 `.env` 文件中的配置（默认配置已可直接使用）：

```env
# 数据库配置
SQLITE_PATH=chalk.db

# Redis配置
REDIS_URL=redis://localhost:6379

# 日志配置
LOG_LEVEL=INFO
LOG_TO_CONSOLE=true
LOG_TO_FILE=false

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

### 4. 启动Chalk服务器

在项目根目录运行：

```bash
python chalk-server.py
```

**成功启动的标志:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 停止服务器

按 `Ctrl+C` 优雅停止服务器。

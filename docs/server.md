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

## 验证服务器运行

### 方法1：访问健康检查接口

打开浏览器访问：
```
http://localhost:8000/health
```

应该看到：
```json
{"status": "healthy"}
```

### 方法2：检查WebSocket连接

使用客户端连接测试：
```python
from chalk.client import Client

client = Client("localhost:8000")
success = await client.connect(name="测试用户")
print(f"连接成功: {success}")
```

## 停止服务器

按 `Ctrl+C` 优雅停止服务器。

## 故障排除

### Redis连接失败

**错误信息:** `Connection refused`

**解决方案:**
1. 确认Redis已启动：`redis-cli ping`
2. 检查Redis端口：默认6379
3. 检查防火墙设置

### 端口被占用

**错误信息:** `Address already in use`

**解决方案:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <进程ID> /F

# Linux/Mac
lsof -i :8000
kill -9 <进程ID>
```

### 数据库连接错误

**解决方案:**
1. 清除Redis数据：`redis-cli FLUSHALL`
2. 重启服务器

## 生产环境部署

生产环境建议使用进程管理器：

**使用supervisor:**
```ini
[program:chalk-server]
command=/path/to/.venv/bin/python chalk-server.py
directory=/path/to/chalk-ai
autostart=true
autorestart=true
```

**使用systemd:**
```ini
[Unit]
Description=Chalk Server
After=network.target redis.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/chalk-ai
ExecStart=/path/to/.venv/bin/python chalk-server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 日志管理

服务器日志输出到标准输出，生产环境建议：

1. 重定向到文件：`python chalk-server.py > server.log 2>&1`
2. 使用日志轮转：`logrotate`配置
3. 集成日志系统：Elasticsearch、Grafana等

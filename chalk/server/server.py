"""  
Chalk Server - 服务器启动封装

提供开箱即用的服务器启动能力
"""
import sys
import multiprocessing
from typing import Optional

from fastapi import FastAPI
import redis as redis_sync
from huey.consumer import Consumer

from .endpoints import router
from .logger import get_logger
from .db import init_database, Database, UserTable, ChatTable, ChatMemberTable, MessageTable
from .tasks import init_huey

logger = get_logger("ChalkServer")

# 全局 app 实例（用于热加载）
_app = None


def get_app() -> FastAPI:
    """获取或创建 FastAPI 应用实例"""
    global _app
    if _app is None:
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            logger.info("FastAPI 应用启动中...")
            yield
            logger.info("FastAPI 应用正在关闭...")
        
        _app = FastAPI(
            title="Chalk Server",
            description="AI 智能体实时通信服务器",
            version="0.1.0",
            lifespan=lifespan
        )
        
        # 注册路由
        _app.include_router(router)
    
    return _app


class ChalkServer:
    """
    Chalk 服务器
    
    封装 FastAPI + Huey Worker 的启动逻辑，提供极简的使用方式
    
    Examples:
        >>> # 最简单的使用方式
        >>> server = ChalkServer(
        ...     redis_url="redis://localhost:6379",
        ...     db_path="chalk.db"
        ... )
        >>> server.run()
        
        >>> # 自定义配置
        >>> server = ChalkServer(
        ...     redis_url="redis://localhost:6379",
        ...     db_path="my_app.db",
        ...     host="0.0.0.0",
        ...     port=8000,
        ...     workers=4
        ... )
        >>> server.run()
        
        >>> # 从环境变量读取（开发者自己管理）
        >>> import os
        >>> server = ChalkServer(
        ...     redis_url=os.getenv("REDIS_URL"),
        ...     db_path=os.getenv("DB_PATH")
        ... )
        >>> server.run()
    """
    
    def __init__(
        self,
        redis_url: str,
        db_path: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int = 2
    ):
        """
        初始化 Chalk 服务器
        
        Args:
            redis_url: Redis 连接地址（必填）
            db_path: SQLite 数据库路径（必填）
            host: 服务监听地址，默认 0.0.0.0
            port: 服务监听端口，默认 8000
            workers: Huey Worker 数量，默认 2
        """
        self.redis_url = redis_url
        self.db_path = db_path
        self.host = host
        self.port = port
        self.workers = workers
        
        # 初始化数据库
        init_database(db_path)
        
        # 初始化 Huey
        init_huey(redis_url)
        
        # 内部管理的组件
        self._app: Optional[FastAPI] = None
        self._server_process: Optional[multiprocessing.Process] = None
    
    def _validate_config(self):
        """验证必备配置"""
        errors = []
        
        # 检查 Redis URL
        if not self.redis_url:
            errors.append("❌ 缺少 Redis 配置")
        
        # 检查数据库路径
        if not self.db_path:
            errors.append("❌ 缺少数据库路径配置")
        
        # 检查端口范围
        if self.port < 1 or self.port > 65535:
            errors.append(f"❌ 端口号无效: {self.port}，必须在 1-65535 之间")
        
        if errors:
            logger.error("配置验证失败:")
            for error in errors:
                logger.error(f"  {error}")
            raise ValueError("缺少必备配置，服务无法启动")
        
        logger.info(f"✅ 配置验证通过")
        logger.info(f"   Redis: {self.redis_url}")
        logger.info(f"   Database: {self.db_path}")
    
    def _check_redis_connection(self):
        """检查 Redis 连接"""
        logger.info("正在检查 Redis 连接...")
        
        try:
            # 使用同步 Redis 客户端进行检查
            client = redis_sync.from_url(self.redis_url, decode_responses=True)
            client.ping()
            client.close()
            logger.info("✅ Redis 连接正常")
            
        except redis_sync.ConnectionError as e:
            logger.error(f"❌ Redis 连接失败: 无法连接到 {self.redis_url}")
            logger.error(f"   错误信息: {e}")
            logger.info("")
            logger.info("💡 请确保 Redis 已启动:")
            logger.info("   方式1: redis-server")
            logger.info("   方式2: docker run -d -p 6379:6379 redis")
            logger.info("")
            raise ConnectionError(f"无法连接到 Redis: {self.redis_url}")
        except redis_sync.TimeoutError as e:
            logger.error(f"❌ Redis 连接超时: {self.redis_url}")
            logger.error(f"   错误信息: {e}")
            raise ConnectionError(f"Redis 连接超时: {self.redis_url}")
        except Exception as e:
            logger.error(f"❌ Redis 检查失败: {e}")
            raise
    
    def _check_database(self):
        """检查数据库状态，如果表不存在则创建"""
        logger.info("正在检查数据库...")
        
        try:
            # 创建 Database 实例（复用已初始化的代理）
            db = Database()
            db.db.connect()
            
            # 检查表是否存在，不存在则创建
            tables = [UserTable, ChatTable, ChatMemberTable, MessageTable]
            created_tables = []
            
            for table in tables:
                if not table.table_exists():
                    logger.info(f"创建新表: {table._meta.table_name}")
                    table.create_table()
                    created_tables.append(table._meta.table_name)
            
            db.db.close()
            
            if created_tables:
                logger.info(f"✅ 数据库检查完成，创建了 {len(created_tables)} 个表")
            else:
                logger.info("✅ 数据库检查完成，所有表已存在")
            
        except PermissionError as e:
            logger.error(f"❌ SQLite 权限错误: 无法访问 {self.db_path}")
            logger.error(f"   错误信息: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 数据库检查失败: {e}")
            raise
    
    def _start_uvicorn_server(self, host: str, port: int):
        """在独立进程中启动 FastAPI 服务器"""
        import uvicorn
        
        logger = get_logger("FastAPI")
        logger.info(f"✅ FastAPI 服务器启动于 http://{host}:{port}")
        
        uvicorn.run(
            "chalk.server.server:get_app",
            host=host,
            port=port,
            log_level="info",
            factory=True
        )
    
    def _start_huey_worker(self):
        """在主线程中启动 Huey Worker"""
        from chalk.server.tasks import huey

        logger.info("=" * 60)
        logger.info("🐱 Huey Worker 启动中...")
        logger.info(f"ℹ️  Huey 实例: {huey.name}")
        logger.info(f"ℹ️  工作线程数: {self.workers}")
        logger.info("=" * 60)
        
        # 配置 consumer
        consumer = Consumer(
            huey,
            workers=self.workers,
            worker_type='thread',
            initial_delay=0.1,
            backoff=1.15,
            max_delay=10.0,
            scheduler_interval=1,
            periodic=True,
            check_worker_health=True,
            health_check_interval=10,
        )
        
        logger.info("✅ Huey Worker 已启动")
        consumer.run()
    
    def run(self):
        """
        启动 Chalk 服务器
        
        会同时启动:
        1. FastAPI HTTP/WebSocket 服务器（独立进程）
        2. Huey 异步任务 Worker（主线程）
        
        Raises:
            ValueError: 配置验证失败
            ConnectionError: Redis 连接失败
            RuntimeError: 环境检查失败
        """
        try:
            # 1. 环境检查
            logger.info("=" * 60)
            logger.info("🚀 Chalk Server 启动中...")
            logger.info("=" * 60)
            
            # 2. 配置验证
            self._validate_config()
            
            # 3. Redis 连接检查
            self._check_redis_connection()
            
            # 4. 数据库检查
            self._check_database()
            
            # 5. 打印启动信息
            logger.info("=" * 60)
            logger.info(f"📍 FastAPI Server: http://{self.host}:{self.port}")
            logger.info(f"📍 Huey Worker: {self.workers} threads")
            logger.info("=" * 60)
            
            # 6. 启动 FastAPI 服务器（独立进程）
            self._server_process = multiprocessing.Process(
                target=self._start_uvicorn_server,
                args=(self.host, self.port)
            )
            self._server_process.start()
            logger.info("✅ FastAPI 服务器进程已启动")
            
            # 7. 启动 Huey Worker（主线程）
            self._start_huey_worker()
            
        except KeyboardInterrupt:
            logger.info("")
            logger.info("收到停止信号，正在关闭服务...")
            self._shutdown()
            
        except Exception as e:
            logger.error(f"❌ 服务启动失败: {str(e)}", exc_info=True)
            self._shutdown()
            sys.exit(1)
    
    def _shutdown(self):
        """优雅关闭服务"""
        if self._server_process and self._server_process.is_alive():
            logger.info("正在关闭 FastAPI 服务器...")
            self._server_process.terminate()
            self._server_process.join(timeout=5)
            
            if self._server_process.is_alive():
                logger.warning("强制终止 FastAPI 服务器")
                self._server_process.kill()
        
        logger.info("✅ 所有服务已关闭")

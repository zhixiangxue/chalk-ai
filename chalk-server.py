#!/usr/bin/env python3
"""
Chalk Server - 统一启动脚本

同时启动 FastAPI 服务器和 Huey Worker
"""
import sys
import multiprocessing
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chalk.server.config import get_settings
from chalk.server.endpoints import router
from chalk.server.init import migrate_database, check_environment
from chalk.server.logger import get_logger

logger = get_logger("ChalkServer")


def start_uvicorn_server(host: str, port: int):
    """在独立进程中启动 FastAPI 服务器"""
    import uvicorn
    from chalk.server.logger import get_logger
    
    logger = get_logger("FastAPI")
    logger.info(f"✅ FastAPI 服务器启动于 http://{host}:{port}")
    
    uvicorn.run(
        "chalk-server:app",
        host=host,
        port=port,
        log_level="info"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行 - 只进行迁移，不重置数据库
    try:
        migrate_database()
        logger.info("✅ 数据库连接检查完成")
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        logger.info("💡 请先运行: python init_db.py --migrate")
        raise
    
    yield
    
    # 关闭时执行（清理代码）
    logger.info("正在关闭服务...")


# 获取配置
settings = get_settings()

app = FastAPI(lifespan=lifespan)

# 注册路由
app.include_router(router)

if __name__ == "__main__":
    # 在启动前进行环境检查
    if not check_environment():
        logger.error("❌ 环境检查失败，无法启动服务")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("🚀 Chalk Server 启动中...")
    logger.info(f"📍 FastAPI: http://{settings.host}:{settings.port}")
    logger.info(f"📍 Huey Worker: 主线程")
    logger.info("=" * 60)
    
    # 在独立进程中启动 FastAPI 服务器
    server_process = multiprocessing.Process(
        target=start_uvicorn_server,
        args=(settings.host, settings.port)
    )
    server_process.start()
    logger.info("✅ FastAPI 服务器进程已启动")
    
    try:
        # 在主线程中启动 Huey Worker
        from chalk.server.tasks import huey
        from huey.consumer import Consumer

        logger.info("=" * 60)
        logger.info("🐱 Huey Worker 启动中...")
        logger.info(f"ℹ️ Huey 实例: {huey.name}")
        logger.info("=" * 60)
        
        # 配置 consumer 参数
        consumer = Consumer(
            huey,
            workers=2,  # 工作进程数
            worker_type='thread',  # 使用线程而不是进程
            initial_delay=0.1,  # 初始延迟
            backoff=1.15,  # 退避因子
            max_delay=10.0,  # 最大延迟
            scheduler_interval=1,  # 调度器间隔
            periodic=True,  # 启用定期任务
            check_worker_health=True,  # 启用工作进程健康检查
            health_check_interval=10,  # 健康检查间隔
        )
        
        logger.info("✅ Huey Worker 已启动")
        consumer.run()
        
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭服务...")
        server_process.terminate()
        server_process.join()
        logger.info("✅ 所有服务已关闭")
    except Exception as e:
        logger.error(f"❌ Huey Worker 启动失败: {str(e)}", exc_info=True)
        server_process.terminate()
        server_process.join()
        sys.exit(1)

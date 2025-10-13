"""
统一的日志配置模块

使用 loguru 提供灵活的日志配置，支持：
- 统一的日志格式
- 可配置的日志级别
- 输出到控制台、文件或两者
- 环境变量配置
"""
import os
import sys
from pathlib import Path
from loguru import logger

# 移除默认的 handler
logger.remove()

# 从环境变量读取日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", 
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "false").lower() == "true"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/chalk-server.log")

def setup_logger():
    """设置 loguru 日志器"""
    
    # 控制台输出
    if LOG_TO_CONSOLE:
        logger.add(
            sys.stdout,
            format=LOG_FORMAT,
            level=LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    
    # 文件输出
    if LOG_TO_FILE:
        # 确保日志目录存在
        log_file = Path(LOG_FILE_PATH)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            LOG_FILE_PATH,
            format=LOG_FORMAT,
            level=LOG_LEVEL,
            rotation="10 MB",  # 日志轮转
            retention="30 days",  # 保留30天
            compression="zip",  # 压缩旧日志
            backtrace=True,
            diagnose=True
        )
    
    logger.info(f"日志系统已初始化 - 级别: {LOG_LEVEL}, 控制台: {LOG_TO_CONSOLE}, 文件: {LOG_TO_FILE}")

def get_logger(name: str = None):
    """
    获取 logger 实例
    
    Args:
        name: 模块名称，用于日志标识
        
    Returns:
        loguru.Logger: 配置好的 logger 实例
    """
    if name:
        return logger.bind(name=name)
    return logger

# 初始化日志系统（导入时自动执行）
setup_logger()

# 导出主要接口
__all__ = ["logger", "get_logger", "setup_logger"]
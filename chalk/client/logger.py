"""
客户端日志系统

简化版日志系统，不依赖server模块
"""
import sys
from datetime import datetime
from typing import Optional


class ClientLogger:
    """简化的客户端日志器"""
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or "ChalkClient"
    
    def _log(self, level: str, message: str):
        """内部日志方法"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {level.upper()} [{self.name}] {message}"
        print(log_msg, file=sys.stderr if level == "error" else sys.stdout)
    
    def info(self, message: str):
        """信息级别日志"""
        self._log("info", message)
    
    def debug(self, message: str):
        """调试级别日志"""
        self._log("debug", message)
    
    def warning(self, message: str):
        """警告级别日志"""  
        self._log("warning", message)
    
    def error(self, message: str):
        """错误级别日志"""
        self._log("error", message)
    
    def success(self, message: str):
        """成功级别日志"""
        self._log("success", message)


def get_logger(name: str = None) -> ClientLogger:
    """
    获取客户端logger实例
    
    Args:
        name: 模块名称，用于日志标识
        
    Returns:
        ClientLogger: 配置好的logger实例
    """
    return ClientLogger(name)


# 默认logger
logger = get_logger("ChalkClient")

# 导出接口
__all__ = ["logger", "get_logger", "ClientLogger"]
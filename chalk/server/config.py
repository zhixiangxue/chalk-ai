import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


def find_env_file() -> Optional[str]:
    """
    智能查找.env文件
    
    查找顺序：
    1. 环境变量 CHALK_ENV_FILE 指定的路径
    2. 当前工作目录
    3. 当前工作目录的父目录（向上最多3级）
    4. 用户home目录下的 .chalk/.env
    """
    # 1. 优先使用环境变量指定的路径
    env_path = os.getenv('CHALK_ENV_FILE')
    if env_path and Path(env_path).exists():
        return env_path
    
    # 2. 从当前工作目录开始查找
    current = Path.cwd()
    for _ in range(4):  # 最多向上查找3级
        env_file = current / '.env'
        if env_file.exists():
            return str(env_file)
        if current.parent == current:  # 到达根目录
            break
        current = current.parent
    
    # 3. 查找用户home目录
    home_env = Path.home() / '.chalk' / '.env'
    if home_env.exists():
        return str(home_env)
    
    # 4. 如果都找不到，返回当前目录的 .env
    return '.env'


class Settings(BaseSettings):
    """应用配置管理"""
    
    # 数据库配置
    sqlite_path: str = Field(default="chalk.db", env="SQLITE_PATH")
    
    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # 开发环境设置
    debug: bool = Field(default=False, env="DEBUG")
    
    class Config:
        # 智能查找.env文件，支持开发和打包后的场景
        env_file = find_env_file()
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量，避免与客户端配置冲突

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 验证关键配置
        self._validate_settings()
    
    def _validate_settings(self):
        """验证配置的有效性"""
        if not self.sqlite_path:
            raise ValueError("SQLITE_PATH must be specified")
        
        if not self.redis_url:
            raise ValueError("REDIS_URL must be specified")
        
        if self.port < 1 or self.port > 65535:
            raise ValueError("PORT must be between 1 and 65535")


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
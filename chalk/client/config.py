"""
客户端配置管理

简化的配置类，仅用于向后兼容旧代码
新的 Client API 不依赖全局配置
"""


class _DummySettings:
    """
    虚拟配置类，仅用于向后兼容
    
    新的 Client API 不使用全局配置，所有参数通过构造函数传递
    保留此类是为了不破坏依赖 settings.base_url 的旧代码
    """
    
    def __init__(self):
        # 默认值，仅用于向后兼容
        self.base_url = "http://localhost:8000"
        self.debug = False


# 全局配置实例（仅用于向后兼容）
settings = _DummySettings()


def get_settings() -> _DummySettings:
    """获取配置实例（仅用于向后兼容）"""
    return settings


# 向后兼容的别名
config = settings

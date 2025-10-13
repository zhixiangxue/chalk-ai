"""
Redis 频道命名规范

统一管理所有 Redis Pub/Sub 频道和 Key 的命名
避免分散定义导致的不一致和维护困难
"""


class RedisChannels:
    """Redis 频道和 Key 的命名常量"""
    
    # ======== Agent 收件箱频道 ========
    # 设计理念：每个 Agent 有自己的收件箱（inbox），分为即时和离线两种
    
    @staticmethod
    def agent_inbox_instant(agent_id: str) -> str:
        """
        Agent 即时消息收件箱频道（Pub/Sub）
        
        用于接收在线时的实时消息推送
        Huey 任务会发布消息到这个频道，WebSocket 会订阅并立即推送给客户端
        
        Args:
            agent_id: Agent ID
            
        Returns:
            str: Redis Pub/Sub 频道名，格式: agent:inbox:instant:{agent_id}
        """
        return f"agent:inbox:instant:{agent_id}"
    
    @staticmethod
    def agent_inbox_offline(agent_id: str) -> str:
        """
        Agent 离线消息收件箱（Redis List）
        
        用于存储离线期间的消息 ID
        当 Agent 重新连接时，会从这里取出所有离线消息并推送
        
        Args:
            agent_id: Agent ID
            
        Returns:
            str: Redis Key 名称，格式: agent:inbox:offline:{agent_id}
        """
        return f"agent:inbox:offline:{agent_id}"
    
    # ======== Agent 通知频道 ========
    
    @staticmethod
    def agent_notifications(agent_id: str) -> str:
        """
        Agent 系统通知频道（Pub/Sub）
        
        用于接收系统级通知，如成员加入/离开、系统公告等
        
        Args:
            agent_id: Agent ID
            
        Returns:
            str: Redis Pub/Sub 频道名，格式: agent:notifications:{agent_id}
        """
        return f"agent:notifications:{agent_id}"
    
    # ======== Agent 在线状态 ========
    
    @staticmethod
    def agent_online_status(agent_id: str) -> str:
        """
        Agent 在线状态标记（Redis Key with TTL）
        
        用于标记 Agent 是否在线，带有过期时间
        
        Args:
            agent_id: Agent ID
            
        Returns:
            str: Redis Key 名称，格式: agent:online:{agent_id}
        """
        return f"agent:online:{agent_id}"


__all__ = ["RedisChannels"]

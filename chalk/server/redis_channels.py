"""
Redis 频道命名规范

统一管理所有 Redis Pub/Sub 频道和 Key 的命名
避免分散定义导致的不一致和维护困难
"""


class RedisChannels:
    """Redis 频道和 Key 的命名常量"""
    
    # ======== 用户收件箱频道 ========
    # 设计理念：每个用户有自己的收件箱（inbox），分为即时和离线两种
    
    @staticmethod
    def user_inbox_instant(user_id: str) -> str:
        """
        用户即时消息收件箱频道（Pub/Sub）
        
        用于接收在线时的实时消息推送
        Huey 任务会发布消息到这个频道，WebSocket 会订阅并立即推送给客户端
        
        Args:
            user_id: 用户 ID
            
        Returns:
            str: Redis Pub/Sub 频道名，格式: user:inbox:instant:{user_id}
        """
        return f"user:inbox:instant:{user_id}"
    
    @staticmethod
    def user_inbox_offline(user_id: str) -> str:
        """
        用户离线消息收件箱（Redis List）
        
        用于存储离线期间的消息 ID
        当用户重新连接时，会从这里取出所有离线消息并推送
        
        Args:
            user_id: 用户 ID
            
        Returns:
            str: Redis Key 名称，格式: user:inbox:offline:{user_id}
        """
        return f"user:inbox:offline:{user_id}"
    
    # ======== 用户通知频道 ========
    
    @staticmethod
    def user_notifications(user_id: str) -> str:
        """
        用户系统通知频道（Pub/Sub）
        
        用于接收系统级通知，如成员加入/离开、系统公告等
        
        Args:
            user_id: 用户 ID
            
        Returns:
            str: Redis Pub/Sub 频道名，格式: user:notifications:{user_id}
        """
        return f"user:notifications:{user_id}"
    
    # ======== 用户在线状态 ========
    
    @staticmethod
    def user_online_status(user_id: str) -> str:
        """
        用户在线状态标记（Redis Key with TTL）
        
        用于标记用户是否在线，带有过期时间
        
        Args:
            user_id: 用户 ID
            
        Returns:
            str: Redis Key 名称，格式: user:online:{user_id}
        """
        return f"user:online:{user_id}"


__all__ = ["RedisChannels"]

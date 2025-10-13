import json
from uuid import UUID
from typing import List, Dict, Optional
from datetime import datetime

import redis.asyncio as redis

from .models import Message
from .redis_channels import RedisChannels


class RedisClient:
    """Redis 客户端 - 支持 Pub/Sub 和离线消息管理"""
    
    def __init__(self, url: str):
        self.url = url
        self.redis = None
        self.pubsub = None

    async def connect(self):
        """连接到Redis服务器"""
        try:
            self.redis = redis.from_url(self.url, decode_responses=True)
            # 测试连接
            await self.redis.ping()
        except Exception as e:
            print(f"Warning: Redis connection failed: {e}")
            print("Continuing without Redis functionality...")
            self.redis = None

    async def disconnect(self):
        """断开Redis连接"""
        if self.pubsub:
            await self.pubsub.aclose()
            self.pubsub = None
        if self.redis:
            await self.redis.aclose()
    
    # ======== Pub/Sub 方法 ========
    
    async def publish_to_channel(self, channel: str, message: str) -> bool:
        """
        发布消息到指定频道
        
        Args:
            channel: 频道名
            message: 消息内容
            
        Returns:
            bool: 是否发布成功
        """
        if not self.redis:
            return False
        
        try:
            result = await self.redis.publish(channel, message)
            return result > 0  # 返回接收者数量
        except Exception as e:
            print(f"Warning: Failed to publish message to channel {channel}: {e}")
            return False
    
    async def subscribe_channels(self, channels: list) -> bool:
        """
        订阅多个频道
        
        Args:
            channels: 频道名列表
            
        Returns:
            bool: 是否订阅成功
        """
        if not self.redis:
            return False
        
        try:
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe(*channels)
            return True
        except Exception as e:
            print(f"Warning: Failed to subscribe to channels {channels}: {e}")
            return False
    
    async def listen(self):
        """
        监听订阅的频道消息
        
        Yields:
            dict: 消息数据，包括 type, channel, data 等字段
        """
        if not self.pubsub:
            return
        
        try:
            async for message in self.pubsub.listen():
                yield message
        except Exception as e:
            print(f"Warning: Redis listen error: {e}")
            return
    
    # ======== Agent 在线状态管理 ========
    
    async def set_agent_online(self, agent_id: str, ttl: int = 300) -> bool:
        """
        设置 Agent 在线状态
        
        Args:
            agent_id: Agent ID
            ttl: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        if not self.redis:
            return False
        
        try:
            await self.redis.setex(RedisChannels.agent_online_status(agent_id), ttl, "1")
            return True
        except Exception as e:
            print(f"Warning: Failed to set agent online status: {e}")
            return False
    
    async def set_agent_offline(self, agent_id: str) -> bool:
        """
        清除 Agent 在线状态
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: 是否清除成功
        """
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(RedisChannels.agent_online_status(agent_id))
            return True
        except Exception as e:
            print(f"Warning: Failed to clear agent online status: {e}")
            return False
    
    async def is_agent_online(self, agent_id: str) -> bool:
        """
        检查 Agent 是否在线
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: 是否在线
        """
        if not self.redis:
            return False
        
        try:
            result = await self.redis.exists(RedisChannels.agent_online_status(agent_id))
            return bool(result)
        except Exception as e:
            print(f"Warning: Failed to check agent online status: {e}")
            return False
    
    # ======== 简化的离线消息存储方法 ========
    
    async def store_offline_message_id(self, agent_id: str, message_id: str, chat_id: str, timestamp: str) -> bool:
        """
        存储离线消息 ID（统一格式，与 instant 消息保持一致）
        
        Args:
            agent_id: Agent ID
            message_id: 消息 ID
            chat_id: 聊天 ID  
            timestamp: 时间戳
            
        Returns:
            bool: 是否存储成功
        """
        if not self.redis:
            return False
        
        try:
            # 使用 Redis List 存储离线消息 ID（与 instant 格式一致）
            offline_key = RedisChannels.agent_inbox_offline(agent_id)
            message_data = {
                "message_id": message_id,
                "chat_id": chat_id,
                "timestamp": timestamp
            }
            
            # 左推入最新消息
            await self.redis.lpush(offline_key, json.dumps(message_data))
            
            # 限制离线消息数量（保留最近 1000 条）
            await self.redis.ltrim(offline_key, 0, 999)
            
            # 设置过期时间（30天）
            await self.redis.expire(offline_key, 30 * 24 * 60 * 60)
            
            return True
        except Exception as e:
            print(f"Warning: Failed to store offline message: {e}")
            return False
    
    async def get_offline_message_ids(self, agent_id: str, limit: int = 100) -> List[Dict]:
        """
        获取 Agent 的离线消息 ID 列表（统一格式）
        
        Args:
            agent_id: Agent ID
            limit: 限制数量
            
        Returns:
            List[Dict]: 离线消息 ID 列表，格式与 instant 一致
        """
        if not self.redis:
            return []
        
        try:
            offline_key = RedisChannels.agent_inbox_offline(agent_id)
            
            # 获取最新的 limit 条消息
            message_strings = await self.redis.lrange(offline_key, 0, limit - 1)
            
            messages = []
            for msg_str in message_strings:
                try:
                    message_data = json.loads(msg_str)
                    messages.append(message_data)
                except json.JSONDecodeError:
                    continue
            
            return messages
        except Exception as e:
            print(f"Warning: Failed to get offline message IDs: {e}")
            return []
    
    async def clear_offline_message_ids(self, agent_id: str) -> bool:
        """
        清空 Agent 的离线消息 ID（统一命名）
        
        Args:
            agent_id: Agent ID
            
        Returns:
            bool: 是否清空成功
        """
        if not self.redis:
            return False
        
        try:
            offline_key = RedisChannels.agent_inbox_offline(agent_id)
            await self.redis.delete(offline_key)
            return True
        except Exception as e:
            print(f"Warning: Failed to clear offline message IDs: {e}")
            return False
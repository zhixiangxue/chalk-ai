"""
消息对象

包含消息的数据和行为，直接实现业务逻辑
"""
import re
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING, Union
from uuid import UUID

import httpx

from .agent import get_base_url

if TYPE_CHECKING:
    from .chat import Chat
    from .agent import Agent


class Message:
    """消息对象 - 具备完整的行为能力
    
    设计原则：
    1. 简化构造函数，只接受必要参数
    2. reply方法需要Agent参数，更自然
    3. 不依赖客户端对象，直接调用HTTP API
    """
    
    def __init__(self, id: UUID, chat_id: UUID, sender_id: UUID, content: str,
                 type: str = "text", mentions: List[UUID] = None, parent_id: UUID = None, 
                 created_at: datetime = None, timestamp: datetime = None):
        """Message构造函数 - 使用全局配置"""
        self.id = id
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.content = content
        self.type = type
        self.mentions = mentions or []
        self.parent_id = parent_id
        # 兼容两种时间字段
        self.created_at = created_at or timestamp or datetime.now()
        self.timestamp = self.created_at  # 保持兼容性
    
    @property
    def base_url(self) -> str:
        """获取 base_url"""
        return get_base_url()
    
    async def get_chat(self) -> 'Chat':
        """获取所属的聊天对象"""
        from .chat import Chat
        from .agent import Agent
        
        # 从服务端获取 chat 信息
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/chats/{self.chat_id}")
            response.raise_for_status()
            chat_data = response.json()
        
        # 获取创建者
        creator = await Agent.from_id(UUID(chat_data["creator_id"]))
        
        return Chat(
            id=UUID(chat_data["id"]),
            name=chat_data["name"],
            type=chat_data.get("type", "group"),
            created_at=datetime.fromisoformat(chat_data["created_at"]),
            creator=creator
        )
    
    async def get_sender(self) -> 'Agent':
        """获取发送者"""
        from .agent import Agent
        return await Agent.from_id(self.sender_id)
    
    async def reply(self, content: str, agent: 'Agent', mentions: List['Agent'] = None) -> 'Message':
        """回复此消息 - 需要Agent参数更自然
        
        Args:
            content: 回复内容
            agent: 发送回复的代理
            mentions: 提及的代理列表
        """
        # 自动解析提及
        parsed_mentions = re.findall(
            r"@([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", 
            content
        )
        mention_ids = [m.id for m in (mentions or [])]
        mention_ids.extend([UUID(m) for m in parsed_mentions])
        final_mentions = list(set(mention_ids))  # 去重
        
        # 直接调用HTTP接口发送回复
        data = {
            "chat_id": str(self.chat_id),
            "content": content,
            "mentions": [str(uid) for uid in final_mentions],
            "parent_id": str(self.id)
        }
        
        headers = {"X-Agent-ID": str(agent.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/messages", json=data, headers=headers)
            response.raise_for_status()
            msg_data = response.json()
        
        return Message(
            id=UUID(msg_data["id"]),
            chat_id=UUID(msg_data["chat_id"]),
            sender_id=UUID(msg_data["sender_id"]),
            content=msg_data["content"],
            mentions=[UUID(m) for m in msg_data.get("mentions", [])],
            parent_id=UUID(msg_data["parent_id"]) if msg_data.get("parent_id") else None,
            created_at=datetime.fromisoformat(msg_data["timestamp"])
        )
    
    async def get_parent(self) -> Optional['Message']:
        """获取父消息（如果是回复）"""
        if self.parent_id is None:
            return None
        
        # 直接从 API 获取父消息
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/messages/{self.parent_id}")
            response.raise_for_status()
            msg_data = response.json()
        
        return Message(
            id=UUID(msg_data["id"]),
            chat_id=UUID(msg_data["chat_id"]),
            sender_id=UUID(msg_data["sender_id"]),
            content=msg_data["content"],
            mentions=[UUID(m) for m in msg_data.get("mentions", [])],
            parent_id=UUID(msg_data["parent_id"]) if msg_data.get("parent_id") else None,
            created_at=datetime.fromisoformat(msg_data["timestamp"])
        )
    
    async def get_replies(self) -> List['Message']:
        """获取所有回复此消息的消息"""
        # 从 API 获取回复消息
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/messages/{self.id}/replies")
            response.raise_for_status()
            replies_data = response.json()
        
        return [
            Message(
                id=UUID(msg["id"]),
                chat_id=UUID(msg["chat_id"]),
                sender_id=UUID(msg["sender_id"]),
                content=msg["content"],
                mentions=[UUID(m) for m in msg.get("mentions", [])],
                parent_id=UUID(msg["parent_id"]) if msg.get("parent_id") else None,
                created_at=datetime.fromisoformat(msg["timestamp"])
            )
            for msg in replies_data
        ]
    
    def is_mention(self, agent: 'Agent') -> bool:
        """检查是否提及了指定的智能体 - 接受Agent对象"""
        return agent.id in self.mentions
    
    def is_reply(self) -> bool:
        """检查是否是回复消息"""
        return self.parent_id is not None
    
    def __repr__(self):
        return f"Message(id={self.id}, content='{self.content[:30]}...')"
    
    def __eq__(self, other):
        if not isinstance(other, Message):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)
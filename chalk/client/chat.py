"""Chat - 聊天对象"""
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from .user import User
    from .message import Message, MessageRef
    from .client import Client


class Chat:
    """聊天对象"""
    
    def __init__(
        self,
        id: UUID,
        name: str,
        creator: 'User',
        created_at: datetime,
        type: str = "group",
        client: Optional['Client'] = None
    ):
        self.id = id
        self.name = name
        self.type = type  # "group" 或 "direct"
        self.creator = creator
        self.created_at = created_at
        self._client = client
    
    def is_direct(self) -> bool:
        """是否是私聊"""
        return self.type == "direct"
    
    def is_group(self) -> bool:
        """是否是群聊"""
        return self.type == "group"
    
    async def send(self, content: str, ref: Optional['MessageRef'] = None) -> 'Message':
        """发送消息"""
        if not self._client:
            raise RuntimeError("Chat未绑定client")
        return await self._client.send_message(self.id, content, ref)
    
    async def get_messages(self, limit: int = 50) -> List['Message']:
        """获取消息列表"""
        if not self._client:
            raise RuntimeError("Chat未绑定client")
        return await self._client.get_messages(self.id, limit)
    
    async def get_members(self) -> List['User']:
        """获取成员列表"""
        if not self._client:
            raise RuntimeError("Chat未绑定client")
        return await self._client.get_members(self.id)
    
    def __repr__(self):
        return f"Chat(name='{self.name}')"

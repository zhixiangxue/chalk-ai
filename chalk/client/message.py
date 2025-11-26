"""Message - 消息对象"""
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING, Dict
from uuid import UUID

if TYPE_CHECKING:
    from .user import User
    from .chat import Chat
    from .client import Client


class MessageRef:
    """消息引用 - 用于回复"""
    
    def __init__(self, message_id: UUID, content: str, sender_name: str, timestamp: datetime):
        self.message_id = message_id
        self.content = content
        self.sender_name = sender_name
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict:
        return {
            "message_id": str(self.message_id),
            "content": self.content,
            "sender_name": self.sender_name,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MessageRef':
        return cls(
            message_id=UUID(data["message_id"]),
            content=data["content"],
            sender_name=data["sender_name"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class Message:
    """消息对象"""
    
    def __init__(
        self,
        id: UUID,
        chat_id: UUID,
        sender: 'User',
        content: str,
        mentions: List[UUID] = None,
        ref: Optional[MessageRef] = None,
        timestamp: datetime = None,
        client: Optional['Client'] = None
    ):
        self.id = id
        self.chat_id = chat_id
        self.sender = sender
        self.content = content
        self.mentions = mentions or []
        self.ref = ref
        self.timestamp = timestamp or datetime.now()
        self._client = client
    
    async def get_chat(self) -> 'Chat':
        """获取所属聊天"""
        if not self._client:
            raise RuntimeError("Message未绑定client")
        return await self._client.get_chat(self.chat_id)
    
    async def reply(self, content: str) -> 'Message':
        """回复此消息"""
        if not self._client:
            raise RuntimeError("Message未绑定client")
        
        chat = await self.get_chat()
        ref = MessageRef(self.id, self.content, self.sender.name, self.timestamp)
        return await chat.send(content, ref=ref)
    
    def __repr__(self):
        preview = self.content[:20] + "..." if len(self.content) > 20 else self.content
        return f"Message({self.sender.name}: {preview})"

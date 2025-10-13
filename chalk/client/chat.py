"""
聊天对象

包含聊天的数据和行为，直接实现业务逻辑
"""
import re
from datetime import datetime
from typing import List, Optional, Union, Dict, TYPE_CHECKING
from uuid import UUID

import httpx

from .agent import Agent, get_base_url
from .message import Message

if TYPE_CHECKING:
    from .client import Client


class Chat:
    """聊天对象 - 具备完整的行为能力 """
    
    def __init__(self, id: UUID, name: str = None, type: str = "group", created_at: datetime = None, 
                 creator: Agent = None, client: Optional['Client'] = None):
        """简化构造函数
        
        Args:
            id: 聊天ID
            name: 聊天名称
            type: 聊天类型
            created_at: 创建时间
            creator: 创建者Agent（用于管理操作）
            client: Client 对象引用（用于获取当前agent和WebSocket发送消息）
        """
        self.id = id
        self.name = name
        self.type = type
        self.created_at = created_at or datetime.now()
        self.creator = creator  # 创建者Agent
        self.client: Optional['Client'] = client  # Client 引用
        self._members_cache = None
    
    @property
    def base_url(self) -> str:
        """获取 base_url"""
        return get_base_url()
    
    @classmethod
    async def create(cls, name: str, creator: Agent, chat_type: str = "group", members: List[Agent] = None) -> 'Chat':
        """创建新聊天
        
        Args:
            name: 聊天名称
            creator: 创建者Agent
            chat_type: 聊天类型 ('group' 或 'private')
            members: 初始成员列表（不包括创建者，创建者会自动加入）
        """
        data = {
            "type": chat_type,
            "name": name,
            "members": [str(m.id) for m in (members or [])]
        }
        
        headers = {"X-Agent-ID": str(creator.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{get_base_url()}/chats", json=data, headers=headers)
            response.raise_for_status()
            chat_data = response.json()
        
        return cls(
            id=UUID(chat_data["id"]),
            name=chat_data["name"],
            creator=creator
        )
    
    @classmethod
    async def from_id(cls, chat_id: UUID, operator: Agent) -> 'Chat':
        """从ID恢复聊天
        
        Args:
            chat_id: 聊天ID
            operator: 请求者Agent（用于验证权限）
        """
        headers = {"X-Agent-ID": str(operator.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{get_base_url()}/chats/{chat_id}", headers=headers)
            response.raise_for_status()
            chat_data = response.json()
        
        # 获取创建者Agent
        creator = await Agent.from_id(UUID(chat_data["creator_id"]))
        
        return cls(
            id=UUID(chat_data["id"]),
            name=chat_data["name"],
            creator=creator
        )
    
    async def send(self, content: Union[str, Message], mentions: List[Agent] = None) -> Message:
        """发送消息（使用当前client的agent身份）
        
        Args:
            content: 消息内容（字符串）或消息对象
            mentions: 提及的代理列表
        """
        if not self.client or not self.client.agent:
            raise ValueError("聊天对象未绑定client，无法发送消息")
        
        if isinstance(content, Message):
            # 如果传入的是Message对象，直接使用其内容
            message_content = content.content
            message_mentions = content.mentions or []
            parent_id = content.parent_id
        else:
            # 如果传入的是字符串，构造消息数据
            message_content = content
            message_mentions = [m.id for m in (mentions or [])]
            parent_id = None
            
            # 自动解析提及
            parsed_mentions = re.findall(
                r"@([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", 
                message_content
            )
            message_mentions.extend([UUID(m) for m in parsed_mentions])
            message_mentions = list(set(message_mentions))  # 去重
        
        # 如果有 client 引用，使用 WebSocket 发送
        if self.client and self.client._connected:
            return await self._send_via_websocket(message_content, message_mentions, parent_id)
        else:
            # 否则使用 HTTP 发送（向后兼容）
            return await self._send_via_http(message_content, message_mentions, parent_id)
    
    async def _send_via_websocket(self, content: str, mentions: List[UUID], parent_id: Optional[UUID]) -> Message:
        """通过 WebSocket 发送消息"""
        import json
        from uuid import uuid4
        
        # 构造消息数据
        message_data = {
            "type": "client_message",
            "data": {
                "chat_id": str(self.id),
                "content": content,
                "type": "text",
                "mentions": [str(m) for m in mentions]
            }
        }
        
        if parent_id:
            message_data["data"]["parent_id"] = str(parent_id)
        
        # 发送消息
        await self.client._websocket.send(json.dumps(message_data))
        
        # 注意：WebSocket 发送是异步的，我们需要返回一个 Message 对象
        # 但实际的 message_id 是服务端生成的，我们这里返回一个临时对象
        # 真实的 Message 会通过 server_ack 或 server_message 事件返回
        temp_message = Message(
            id=uuid4(),  # 临时 ID
            chat_id=self.id,
            sender_id=self.client.agent.id,
            content=content,
            type="text",
            mentions=mentions,
            parent_id=parent_id,
            created_at=datetime.now()
        )
        
        return temp_message
    
    async def _send_via_http(self, content: str, mentions: List[UUID], parent_id: Optional[UUID]) -> Message:
        """通过 HTTP 发送消息（向后兼容）"""
        # 直接调用HTTP接口发送消息（使用client的agent身份）
        data = {
            "chat_id": str(self.id),
            "content": content,
            "mentions": [str(uid) for uid in mentions]
        }
        if parent_id:
            data["parent_id"] = str(parent_id)
        
        headers = {"X-Agent-ID": str(self.client.agent.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/messages", json=data, headers=headers)
            response.raise_for_status()
            msg_data = response.json()
        
        return Message(
            id=UUID(msg_data["id"]),
            chat_id=self.id,
            sender_id=UUID(msg_data["sender_id"]),
            content=msg_data["content"],
            mentions=[UUID(m) for m in msg_data.get("mentions", [])],
            parent_id=UUID(msg_data["parent_id"]) if msg_data.get("parent_id") else None,
            created_at=datetime.fromisoformat(msg_data["timestamp"])
        )
    
    async def get_messages(self, limit: int = 50, offset: int = 0) -> List[Message]:
        """获取聊天消息"""
        params = {"limit": limit, "offset": offset}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/chats/{self.id}/messages", params=params)
            response.raise_for_status()
            messages_data = response.json()
        
        return [
            Message(
                id=UUID(msg["id"]),
                chat_id=self.id,
                sender_id=UUID(msg["sender_id"]),
                content=msg["content"],
                mentions=[UUID(m) for m in msg.get("mentions", [])],
                parent_id=UUID(msg["parent_id"]) if msg.get("parent_id") else None,
                created_at=datetime.fromisoformat(msg["timestamp"])
            )
            for msg in messages_data
        ]
    
    async def get_members(self) -> List[Agent]:
        """获取聊天成员"""
        if self._members_cache is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/chats/{self.id}/members")
                response.raise_for_status()
                members_data = response.json()
            
            self._members_cache = [
                Agent(
                    id=UUID(member["id"]),
                    name=member["name"]
                )
                for member in members_data
            ]
        return self._members_cache
    
    async def add_member(self, member: Agent):
        """添加成员（使用创建者权限）
        
        Args:
            member: 要添加的成员
        """
        if not self.creator:
            raise ValueError("Chat对象未绑定创建者，无法添加成员")
        
        headers = {"X-Agent-ID": str(self.creator.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/chats/{self.id}/members/{member.id}", headers=headers)
            response.raise_for_status()
        
        # 清空缓存
        self._members_cache = None
        return response.json()
    
    async def remove_member(self, member: Agent):
        """移除成员（使用创建者权限）
        
        Args:
            member: 要移除的成员
        """
        if not self.creator:
            raise ValueError("Chat对象未绑定创建者，无法移除成员")
        
        headers = {"X-Agent-ID": str(self.creator.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/chats/{self.id}/members/{member.id}", headers=headers)
            response.raise_for_status()
        
        # 清空缓存
        self._members_cache = None
        return response.json()
    
    async def delete(self):
        """删除聊天（仅创建者可用）"""
        if not self.creator:
            raise ValueError("Chat对象未绑定创建者，无法删除聊天")
        
        headers = {"X-Agent-ID": str(self.creator.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/chats/{self.id}", headers=headers)
            
            if response.status_code == 403:
                raise PermissionError("只有创建者才能删除聊天")
            elif response.status_code not in [200, 404]:
                raise ValueError(f"删除聊天失败: {response.text}")
        
        return True
    
    async def destroy(self):
        """删除/解散聊天（别名方法）"""
        return await self.delete()
    
    async def leave(self):
        """离开聊天（如果是创建者则删除聊天）"""
        if not self.client or not self.client.agent:
            raise ValueError("聊天对象未绑定client，无法离开聊天")
        
        headers = {"X-Agent-ID": str(self.client.agent.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/chats/{self.id}/members/{self.client.agent.id}", headers=headers)
            response.raise_for_status()
        
        return True
    
    async def history(self, page: int = 1, page_size: int = 100) -> List[Message]:
        """获取聊天历史消息（支持分页）"""
        return await self.get_messages(limit=page_size, offset=(page - 1) * page_size)
    
    async def info(self) -> Dict:
        """获取聊天的详细信息"""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type,
            "creator_id": str(self.creator.id) if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "members": await self.get_members()
        }
    
    def __repr__(self):
        return f"Chat(id={self.id}, name='{self.name}')"
    
    def __eq__(self, other):
        if not isinstance(other, Chat):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)
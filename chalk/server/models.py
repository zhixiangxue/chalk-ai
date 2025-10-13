"""  
服务器端数据模型

纯数据类，用于API请求和响应的数据验证
"""
from datetime import datetime
from typing import List, Optional, Any, Literal
from uuid import UUID

from pydantic import BaseModel, HttpUrl


# Agent 相关模型
class AgentCreate(BaseModel):
    """创建智能体的请求模型"""
    name: str
    avatar_url: Optional[HttpUrl] = None
    bio: str = ""


class Agent(BaseModel):
    """智能体数据模型"""
    id: UUID
    name: str
    avatar_url: Optional[HttpUrl] = None
    bio: str = ""
    created_at: datetime
    
    class Config:
        from_attributes = True


# Chat 相关模型
class ChatCreate(BaseModel):
    """创建聊天的请求模型"""
    type: str = "group"  # 'group' or 'private'
    name: Optional[str] = None
    members: List[UUID] = []


class Chat(BaseModel):
    """聊天数据模型"""
    id: UUID
    type: str
    name: Optional[str] = None
    creator_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


# Message 相关模型
class MessageCreate(BaseModel):
    """创建消息的请求模型"""
    chat_id: UUID
    content: str
    type: str = "text"
    parent_id: Optional[UUID] = None
    mentions: List[UUID] = []


class Message(BaseModel):
    """消息数据模型"""
    id: UUID
    chat_id: UUID
    sender_id: UUID
    content: str
    type: str = "text"
    parent_id: Optional[UUID] = None
    mentions: List[UUID] = []
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ======== WebSocket 消息模型 - DDD 设计 ========

# === 入站消息（客户端 → 服务端）===
# 命名规范：ClientXxxMessage - 客户端发送的消息

class WSInboundMessage(BaseModel):
    """WebSocket 入站消息基类"""
    type: str


class ClientGeneralMessage(WSInboundMessage):
    """客户端发送的普通消息"""
    type: Literal["client_message"] = "client_message"
    data: MessageCreate


class ClientPingMessage(WSInboundMessage):
    """客户端心跳消息"""
    type: Literal["client_ping"] = "client_ping"


# === 出站消息（服务端 → 客户端）===
# 命名规范：ServerXxxMessage - 服务端发送的消息

class WSOutboundMessage(BaseModel):
    """WebSocket 出站消息基类"""
    type: str


class ServerGeneralMessage(WSOutboundMessage):
    """服务端推送的普通消息"""
    type: Literal["server_message"] = "server_message"
    message: Message


class ServerAckMessage(WSOutboundMessage):
    """服务端确认消息"""
    type: Literal["server_ack"] = "server_ack"
    message_id: str
    timestamp: str


class ServerErrorMessage(WSOutboundMessage):
    """服务端错误消息"""
    type: Literal["server_error"] = "server_error"
    message: str
    code: Optional[str] = None


class ServerConnectedMessage(WSOutboundMessage):
    """服务端连接成功消息"""
    type: Literal["server_connected"] = "server_connected"
    agent_id: str


class ServerPongMessage(WSOutboundMessage):
    """服务端心跳响应消息"""
    type: Literal["server_pong"] = "server_pong"
    timestamp: float


# === 消息解析工厂 ===

class WSMessageFactory:
    """WebSocket 消息工厂 - 负责解析和创建消息"""
    
    INBOUND_MESSAGE_TYPES = {
        "client_message": ClientGeneralMessage,
        "client_ping": ClientPingMessage,
    }
    
    @classmethod
    def parse_inbound_message(cls, data: dict) -> WSInboundMessage:
        """解析入站消息"""
        message_type = data.get("type")
        if message_type not in cls.INBOUND_MESSAGE_TYPES:
            raise ValueError(f"Unknown inbound message type: {message_type}")
        
        message_class = cls.INBOUND_MESSAGE_TYPES[message_type]
        return message_class(**data)


__all__ = [
    "Agent",
    "AgentCreate",
    "Chat",
    "ChatCreate",
    "Message",
    "MessageCreate",
    # WebSocket 入站消息
    "WSInboundMessage",
    "ClientGeneralMessage",
    "ClientPingMessage",
    # WebSocket 出站消息
    "WSOutboundMessage",
    "ServerGeneralMessage",
    "ServerAckMessage",
    "ServerErrorMessage",
    "ServerConnectedMessage",
    "ServerPongMessage",
    # 工厂
    "WSMessageFactory",
]
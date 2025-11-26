from typing import List
from uuid import UUID

from .db import Database
from .models import MessageCreate, Message, Chat, ChatCreate, User, UserRegister, UserAuth


class UserService:
    def __init__(self, db: Database):
        self.db = db

    async def register_user(self, user_data: UserRegister) -> User:
        return await self.db.register_user(user_data)
    
    async def login_user(self, auth_data: UserAuth) -> User:
        return await self.db.login_user(auth_data)
    
    async def get_user(self, user_id: UUID) -> User:
        return await self.db.get_user(user_id)
    
    async def get_users_by_name(self, name: str) -> List[User]:
        """根据用户名获取所有同名用户"""
        return await self.db.get_users_by_name(name)


class MessageService:
    """
    消息服务 - 简化版本
    
    重构后主要通过 WebSocket 处理消息，HTTP 端点已删除
    """
    
    def __init__(self, db: Database):
        self.db = db
        # 移除 Redis 依赖，消息分发通过 Huey 任务处理

    async def get_message(self, message_id: UUID) -> Message:
        """
        根据 ID 获取消息详情
        
        主要用于内部调用和可能的 API 查询需求
        """
        return await self.db.get_message(message_id)

    async def store_message_only(self, message_data: MessageCreate, sender_id: UUID) -> Message:
        """
        仅存储消息到数据库，不进行分发
        
        这个方法由 WebSocketHandler 使用，分发逻辑由 Huey 任务处理。
        """
        return await self.db.store_message(message_data, sender_id)


class ChatService:
    def __init__(self, db: Database):
        self.db = db

    async def create_chat(self, chat_data: ChatCreate, creator_id: UUID) -> Chat:
        # 验证私聊规则
        if chat_data.type == "direct":
            if len(chat_data.members) != 1:
                raise ValueError("私聊只能有两个成员（创建者 + 1个成员）")
        
        return await self.db.create_chat(chat_data, creator_id)

    async def join_chat(self, chat_id: UUID, user_id: UUID):
        await self.db.join_chat(chat_id, user_id)

    async def leave_chat(self, chat_id: UUID, user_id: UUID) -> bool:
        return await self.db.leave_chat(chat_id, user_id)

    async def delete_chat(self, chat_id: UUID, requester_id: UUID) -> bool:
        return await self.db.delete_chat(chat_id, requester_id)

    async def list_chats(self, user_id: UUID) -> List[Chat]:
        return await self.db.get_chats_for_user(user_id)
    
    async def get_chat(self, chat_id: UUID, requester_id: UUID) -> Chat:
        """获取聊天详细信息（需要验证权限）"""
        return await self.db.get_chat(chat_id, requester_id)

    async def list_members(self, chat_id: UUID) -> List[User]:
        return await self.db.get_chat_members(chat_id)

    async def remove_member(self, chat_id: UUID, user_id: UUID, requester_id: UUID) -> bool:
        return await self.db.remove_member(chat_id, user_id, requester_id)

    async def add_member(self, chat_id: UUID, user_id: UUID, requester_id: UUID) -> bool:
        # 检查是否是私聊
        chat = await self.db.get_chat(chat_id, requester_id)
        if chat.type == "direct":
            raise ValueError("私聊不能添加成员")
        
        return await self.db.add_member(chat_id, user_id, requester_id)

    async def list_messages(self, chat_id: UUID, page: int = 1, page_size: int = 50) -> List[Message]:
        return await self.db.get_chat_messages(chat_id, page, page_size)
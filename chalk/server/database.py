import json
from typing import List
from uuid import UUID

from peewee import DoesNotExist

from .models import Agent, Chat, Message, AgentCreate, ChatCreate, MessageCreate
from .tables import (
    AgentTable, ChatTable, MessageTable, ChatMemberTable, 
    get_database
)


class Database:
    def __init__(self, db_path: str = None):
        # db_path 参数保留以保持接口兼容性，但实际使用配置管理
        self.db = get_database()

    async def connect(self):
        """连接数据库"""
        if self.db.is_closed():
            self.db.connect()

    async def disconnect(self):
        """断开数据库连接"""
        if not self.db.is_closed():
            self.db.close()

    async def create_agent(self, agent: AgentCreate) -> Agent:
        """创建代理 - 最简洁的微信账号注册"""
        
        db_agent = AgentTable.create(
            name=agent.name,
            avatar_url=str(agent.avatar_url) if agent.avatar_url else None,
            bio=agent.bio
        )
        
        # 返回简洁的Agent对象
        return Agent(
            id=db_agent.id,
            created_at=db_agent.created_at,
            name=db_agent.name,
            avatar_url=agent.avatar_url,
            bio=db_agent.bio
        )
    
    async def get_agent(self, agent_id: UUID) -> Agent:
        """根据ID获取代理信息"""
        try:
            db_agent = AgentTable.get(AgentTable.id == agent_id)
            
            # 处理avatar_url
            from pydantic import HttpUrl
            avatar_url = None
            if db_agent.avatar_url:
                try:
                    avatar_url = HttpUrl(db_agent.avatar_url)
                except:
                    avatar_url = None
            
            return Agent(
                id=db_agent.id,
                created_at=db_agent.created_at,
                name=db_agent.name,
                avatar_url=avatar_url,
                bio=db_agent.bio
            )
        except DoesNotExist:
            raise ValueError(f"Agent with id {agent_id} not found")

    async def create_chat(self, chat: ChatCreate, creator_id: UUID) -> Chat:
        """创建聊天，指定创建者"""
        try:
            creator = AgentTable.get(AgentTable.id == creator_id)
            
            db_chat = ChatTable.create(
                type=chat.type,
                name=chat.name,
                creator=creator
            )
            
            # 创建者自动加入聊天
            ChatMemberTable.create(chat=db_chat, agent=creator)
            
            # 添加其他成员
            for agent_id in chat.members:
                if agent_id != creator_id:  # 避免重复添加创建者
                    try:
                        agent = AgentTable.get(AgentTable.id == agent_id)
                        ChatMemberTable.create(chat=db_chat, agent=agent)
                    except DoesNotExist:
                        pass  # 忽略不存在的代理
            
            return Chat(
                id=db_chat.id,
                type=db_chat.type,
                name=db_chat.name,
                creator_id=db_chat.creator.id,
                created_at=db_chat.created_at
            )
        except DoesNotExist:
            raise ValueError("Creator not found")

    async def join_chat(self, chat_id: UUID, agent_id: UUID):
        """加入聊天"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            agent = AgentTable.get(AgentTable.id == agent_id)
            ChatMemberTable.get_or_create(chat=chat, agent=agent)
        except DoesNotExist:
            pass  # 忽略不存在的聊天或代理

    async def get_message(self, message_id: UUID) -> Message:
        """根据 ID 获取消息详情"""
        try:
            db_message = MessageTable.get(MessageTable.id == message_id)
            
            # 解析 mentions
            mentions_list = json.loads(db_message.mentions) if db_message.mentions else []
            mentions_uuids = [UUID(uid) for uid in mentions_list]
            
            return Message(
                id=db_message.id,
                chat_id=db_message.chat.id,
                sender_id=db_message.sender.id,
                content=db_message.content,
                type=db_message.type,
                parent_id=db_message.parent.id if db_message.parent else None,
                mentions=mentions_uuids,
                timestamp=db_message.timestamp
            )
        except DoesNotExist:
            raise ValueError(f"Message with id {message_id} not found")

    async def store_message(self, message: MessageCreate, sender_id: UUID) -> Message:
        """存储消息"""
        try:
            chat = ChatTable.get(ChatTable.id == message.chat_id)
            sender = AgentTable.get(AgentTable.id == sender_id)
            
            # 处理 mentions
            mentions_json = json.dumps([str(uid) for uid in message.mentions]) if message.mentions else None
            
            # 处理 parent_id
            parent = None
            if message.parent_id:
                try:
                    parent = MessageTable.get(MessageTable.id == message.parent_id)
                except DoesNotExist:
                    pass
            
            db_message = MessageTable.create(
                chat=chat,
                sender=sender,
                content=message.content,
                type=message.type,
                parent=parent,
                mentions=mentions_json
            )
            
            # 解析 mentions
            mentions_list = json.loads(db_message.mentions) if db_message.mentions else []
            mentions_uuids = [UUID(uid) for uid in mentions_list]
            
            return Message(
                id=db_message.id,
                chat_id=db_message.chat.id,
                sender_id=db_message.sender.id,
                content=db_message.content,
                type=db_message.type,
                parent_id=db_message.parent.id if db_message.parent else None,
                mentions=mentions_uuids,
                timestamp=db_message.timestamp
            )
        except DoesNotExist:
            raise ValueError("Chat or sender not found")

    async def get_chats_for_agent(self, agent_id: UUID) -> List[Chat]:
        """获取代理的聊天列表"""
        try:
            agent = AgentTable.get(AgentTable.id == agent_id)
            chat_members = ChatMemberTable.select().where(ChatMemberTable.agent == agent)
            chats = []
            for member in chat_members:
                chat = member.chat
                chats.append(Chat(
                    id=chat.id,
                    type=chat.type,
                    name=chat.name,
                    creator_id=chat.creator.id,
                    created_at=chat.created_at
                ))
            return chats
        except DoesNotExist:
            return []
    
    async def get_chat(self, chat_id: UUID, requester_id: UUID) -> Chat:
        """获取聊天详细信息（验证权限）"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            
            # 验证是否是成员
            agent = AgentTable.get(AgentTable.id == requester_id)
            member_relation = ChatMemberTable.get_or_none(
                (ChatMemberTable.chat == chat) & 
                (ChatMemberTable.agent == agent)
            )
            
            if not member_relation:
                raise PermissionError("只有聊天成员才能访问")
            
            return Chat(
                id=chat.id,
                type=chat.type,
                name=chat.name,
                creator_id=chat.creator.id,
                created_at=chat.created_at
            )
        except DoesNotExist:
            raise ValueError(f"Chat with id {chat_id} not found")

    async def get_chat_members(self, chat_id: UUID) -> List[Agent]:
        """获取聊天成员列表 - 简洁版本"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            chat_members = ChatMemberTable.select().where(ChatMemberTable.chat == chat)
            agents = []
            for member in chat_members:
                agent = member.agent
                
                # 处理avatar_url
                from pydantic import HttpUrl
                avatar_url = None
                if agent.avatar_url:
                    try:
                        avatar_url = HttpUrl(agent.avatar_url)
                    except:
                        avatar_url = None
                
                agents.append(Agent(
                    id=agent.id,
                    created_at=agent.created_at,
                    name=agent.name,
                    avatar_url=avatar_url,
                    bio=agent.bio
                ))
            return agents
        except DoesNotExist:
            return []
    
    async def get_chat_member_ids(self, chat_id: UUID) -> List[UUID]:
        """获取聊天成员ID列表（用于Redis消息推送）"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            chat_members = ChatMemberTable.select().where(ChatMemberTable.chat == chat)
            return [member.agent.id for member in chat_members]
        except DoesNotExist:
            return []

    async def leave_chat(self, chat_id: UUID, agent_id: UUID) -> bool:
        """退出聊天，如果是创建者退出则自动删除聊天"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            agent = AgentTable.get(AgentTable.id == agent_id)
            
            # 检查是否是创建者
            if chat.creator.id == agent_id:
                # 创建者退出，删除整个聊天
                return await self.delete_chat(chat_id, agent_id)
            else:
                # 普通成员退出
                ChatMemberTable.delete().where(
                    (ChatMemberTable.chat == chat) & 
                    (ChatMemberTable.agent == agent)
                ).execute()
                return True
        except DoesNotExist:
            return False

    async def delete_chat(self, chat_id: UUID, requester_id: UUID) -> bool:
        """删除聊天，只有创建者才能删除"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            
            # 检查权限：只有创建者才能删除
            if chat.creator.id != requester_id:
                raise PermissionError("只有创建者才能删除聊天")
            
            # 删除相关数据（按依赖关系顺序）
            # 1. 删除所有消息
            MessageTable.delete().where(MessageTable.chat == chat).execute()
            
            # 2. 删除所有成员关系
            ChatMemberTable.delete().where(ChatMemberTable.chat == chat).execute()
            
            # 3. 删除聊天本身
            chat.delete_instance()
            
            return True
        except DoesNotExist:
            return False
        except PermissionError:
            raise

    async def get_chat_messages(self, chat_id: UUID, page: int = 1, page_size: int = 50) -> List[Message]:
        """获取聊天消息列表，按时间倒序分页"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 查询消息，按时间倒序
            messages_query = (
                MessageTable
                .select()
                .where(MessageTable.chat == chat)
                .order_by(MessageTable.timestamp.desc())
                .limit(page_size)
                .offset(offset)
            )
            
            messages = []
            for db_message in messages_query:
                # 解析 mentions
                mentions_list = json.loads(db_message.mentions) if db_message.mentions else []
                mentions_uuids = [UUID(uid) for uid in mentions_list]
                
                messages.append(Message(
                    id=db_message.id,
                    chat_id=db_message.chat.id,
                    sender_id=db_message.sender.id,
                    content=db_message.content,
                    type=db_message.type,
                    parent_id=db_message.parent.id if db_message.parent else None,
                    mentions=mentions_uuids,
                    timestamp=db_message.timestamp
                ))
            
            return messages
            
        except DoesNotExist:
            return []

    async def remove_member(self, chat_id: UUID, agent_id: UUID, requester_id: UUID) -> bool:
        """移除成员，只有创建者才能移除其他人"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            agent = AgentTable.get(AgentTable.id == agent_id)
            
            # 检查权限：只有创建者才能踢出成员
            if chat.creator.id != requester_id:
                raise PermissionError("只有创建者才能移除成员")
            
            # 不能移除自己
            if agent_id == requester_id:
                raise ValueError("不能移除自己，请使用退出功能")
            
            # 检查成员是否在聊天中
            member_relation = ChatMemberTable.get_or_none(
                (ChatMemberTable.chat == chat) & 
                (ChatMemberTable.agent == agent)
            )
            
            if not member_relation:
                return False  # 成员不在聊天中
            
            # 移除成员
            member_relation.delete_instance()
            return True
            
        except DoesNotExist:
            return False
        except (PermissionError, ValueError):
            raise

    async def add_member(self, chat_id: UUID, agent_id: UUID, requester_id: UUID) -> bool:
        """添加成员，只有创建者才能添加其他人"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            agent = AgentTable.get(AgentTable.id == agent_id)
            
            # 检查权限：只有创建者才能邀请成员
            if chat.creator.id != requester_id:
                raise PermissionError("只有创建者才能添加成员")
            
            # 检查成员是否已经在聊天中
            existing_member = ChatMemberTable.get_or_none(
                (ChatMemberTable.chat == chat) & 
                (ChatMemberTable.agent == agent)
            )
            
            if existing_member:
                return False  # 成员已经在聊天中
            
            # 添加成员
            ChatMemberTable.create(chat=chat, agent=agent)
            return True
            
        except DoesNotExist:
            return False
        except PermissionError:
            raise
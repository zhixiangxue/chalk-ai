"""
数据库模块 - 一站式解决方案

职责：
1. 定义数据库代理（避免循环导入）
2. 定义所有表结构
3. 提供数据访问层（Database类）
"""
import json
import uuid
from pathlib import Path
from typing import List
from uuid import UUID
from datetime import datetime

from peewee import (
    DatabaseProxy, SqliteDatabase, Model, DoesNotExist,
    UUIDField, CharField, TextField, DateTimeField, ForeignKeyField, CompositeKey
)

from .models import User, Chat, Message, UserRegister, UserAuth, ChatCreate, MessageCreate, MessageRef


# ============================================================================
# 第一部分：数据库代理（核心，避免循环导入）
# ============================================================================

db_proxy = DatabaseProxy()


def init_database(db_path: str):
    """
    初始化数据库代理
    
    Args:
        db_path: SQLite 数据库文件路径
    """
    # 确保数据库目录存在
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建真实的数据库实例
    database = SqliteDatabase(db_path, pragmas={
        'foreign_keys': 1,  # 启用外键约束
        'journal_mode': 'wal',  # 使用 WAL 模式提升并发性能
    })
    
    # 将代理绑定到实际数据库
    db_proxy.initialize(database)


# ============================================================================
# 第二部分：表定义
# ============================================================================

class BaseTable(Model):
    """
    数据库表基类
    
    所有表模型均继承此类，使用统一的数据库代理
    """
    class Meta:
        database = db_proxy  # 使用代理，而非具体数据库


class UserTable(BaseTable):
    """用户数据表 - 基于用户名+密码的账号设计"""
    # 基本标识信息
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=100, unique=True)
    password_hash = CharField()  # 密码哈希
    
    # 档案信息
    avatar_url = CharField(max_length=500, null=True)
    bio = TextField()  # 个人简介和能力说明
    
    # 时间戳
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'users'


class ChatTable(BaseTable):
    """聊天数据表"""
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    type = CharField(max_length=10)  # 'group' or 'private'
    name = CharField(max_length=255, null=True)
    creator = ForeignKeyField(UserTable, backref='created_chats')  # 创建者
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'chats'


class ChatMemberTable(BaseTable):
    """聊天成员关系表"""
    chat = ForeignKeyField(ChatTable, backref='members')
    user = ForeignKeyField(UserTable, backref='chats')
    joined_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'chat_members'
        primary_key = CompositeKey('chat', 'user')


class MessageTable(BaseTable):
    """消息数据表"""
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    chat = ForeignKeyField(ChatTable, backref='messages')
    sender = ForeignKeyField(UserTable, backref='sent_messages')
    content = TextField()
    type = CharField(max_length=20, default='text')
    ref_data = TextField(null=True)  # JSON string - 存储引用消息的快照
    mentions = TextField(null=True)  # JSON string of UUIDs
    timestamp = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'messages'


# ============================================================================
# 第三部分：数据访问层
# ============================================================================

class Database:
    """
    数据访问层 - 封装所有数据库操作
    
    使用示例：
        >>> # 方式1：Database 自己初始化
        >>> db = Database("chalk.db")
        >>> await db.connect()
        >>> 
        >>> # 方式2：外部初始化后使用
        >>> init_database("chalk.db")
        >>> db = Database()
        >>> await db.connect()
    """
    
    def __init__(self, db_path: str = None):
        """
        创建 Database 实例
        
        Args:
            db_path: SQLite 数据库文件路径
                    - 如果提供，则初始化数据库代理
                    - 如果为 None，则使用已初始化的代理
        """
        if db_path:
            # 初始化数据库代理
            init_database(db_path)
        
        # 使用代理
        self.db = db_proxy

    async def connect(self):
        """连接数据库"""
        if self.db.is_closed():
            self.db.connect()

    async def disconnect(self):
        """断开数据库连接"""
        if not self.db.is_closed():
            self.db.close()

    async def register_user(self, user_data: UserRegister) -> User:
        """Register new user"""
        import bcrypt
        
        # Hash password with bcrypt
        password_bytes = user_data.password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        
        db_user = UserTable.create(
            name=user_data.name,
            password_hash=hashed.decode('utf-8'),
            avatar_url=str(user_data.avatar_url) if user_data.avatar_url else None,
            bio=user_data.bio
        )
        
        return User(
            id=db_user.id,
            created_at=db_user.created_at,
            name=db_user.name,
            avatar_url=user_data.avatar_url,
            bio=db_user.bio
        )
    
    async def login_user(self, auth_data: UserAuth) -> User:
        """User login (verify password)"""
        import bcrypt
        
        try:
            db_user = UserTable.get(UserTable.name == auth_data.name)
            
            # Verify password with bcrypt
            password_bytes = auth_data.password.encode('utf-8')
            if not bcrypt.checkpw(password_bytes, db_user.password_hash.encode('utf-8')):
                raise ValueError("密码错误")
            
            # 处理avatar_url
            from pydantic import HttpUrl
            avatar_url = None
            if db_user.avatar_url:
                try:
                    avatar_url = HttpUrl(db_user.avatar_url)
                except:
                    avatar_url = None
            
            return User(
                id=db_user.id,
                created_at=db_user.created_at,
                name=db_user.name,
                avatar_url=avatar_url,
                bio=db_user.bio
            )
        except DoesNotExist:
            raise ValueError(f"用户 {auth_data.name} 不存在")
    
    async def get_user(self, user_id: UUID) -> User:
        """根据ID获取用户信息"""
        try:
            db_user = UserTable.get(UserTable.id == user_id)
            
            # 处理avatar_url
            from pydantic import HttpUrl
            avatar_url = None
            if db_user.avatar_url:
                try:
                    avatar_url = HttpUrl(db_user.avatar_url)
                except:
                    avatar_url = None
            
            return User(
                id=db_user.id,
                created_at=db_user.created_at,
                name=db_user.name,
                avatar_url=avatar_url,
                bio=db_user.bio
            )
        except DoesNotExist:
            raise ValueError(f"User with id {user_id} not found")
    
    async def get_user_by_name(self, name: str) -> User:
        """根据用户名获取用户信息（只返回第一个，已废弃）"""
        users = await self.get_users_by_name(name)
        if not users:
            raise ValueError(f"用户 {name} 不存在")
        return users[0]
    
    async def get_users_by_name(self, name: str) -> List[User]:
        """根据用户名获取所有同名用户"""
        try:
            # 查询所有同名用户
            db_users = UserTable.select().where(UserTable.name == name)
            
            users = []
            for db_user in db_users:
                # 处理avatar_url
                from pydantic import HttpUrl
                avatar_url = None
                if db_user.avatar_url:
                    try:
                        avatar_url = HttpUrl(db_user.avatar_url)
                    except:
                        avatar_url = None
                
                users.append(User(
                    id=db_user.id,
                    created_at=db_user.created_at,
                    name=db_user.name,
                    avatar_url=avatar_url,
                    bio=db_user.bio
                ))
            
            return users
        except Exception as e:
            return []

    async def create_chat(self, chat: ChatCreate, creator_id: UUID) -> Chat:
        """创建聊天，指定创建者"""
        try:
            creator = UserTable.get(UserTable.id == creator_id)
            
            db_chat = ChatTable.create(
                type=chat.type,
                name=chat.name,
                creator=creator
            )
            
            # 创建者自动加入聊天
            ChatMemberTable.create(chat=db_chat, user=creator)
            
            # 添加其他成员
            for user_id in chat.members:
                if user_id != creator_id:  # 避免重复添加创建者
                    try:
                        user = UserTable.get(UserTable.id == user_id)
                        ChatMemberTable.create(chat=db_chat, user=user)
                    except DoesNotExist:
                        pass  # 忽略不存在的用户
            
            return Chat(
                id=db_chat.id,
                type=db_chat.type,
                name=db_chat.name,
                creator_id=db_chat.creator.id,
                created_at=db_chat.created_at
            )
        except DoesNotExist:
            raise ValueError("Creator not found")

    async def join_chat(self, chat_id: UUID, user_id: UUID):
        """加入聊天"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            user = UserTable.get(UserTable.id == user_id)
            ChatMemberTable.get_or_create(chat=chat, user=user)
        except DoesNotExist:
            pass  # 忽略不存在的聊天或用户

    async def get_message(self, message_id: UUID) -> Message:
        """根据 ID 获取消息详情"""
        try:
            db_message = MessageTable.get(MessageTable.id == message_id)
            
            # 解析 mentions
            mentions_list = json.loads(db_message.mentions) if db_message.mentions else []
            mentions_uuids = [UUID(uid) for uid in mentions_list]
            
            # 解析 ref_data
            ref = None
            if db_message.ref_data:
                try:
                    ref_dict = json.loads(db_message.ref_data)
                    ref = MessageRef(
                        message_id=UUID(ref_dict["message_id"]),
                        content=ref_dict["content"],
                        sender_name=ref_dict["sender_name"],
                        timestamp=datetime.fromisoformat(ref_dict["timestamp"])
                    )
                except:
                    pass
            
            # 构造完整的 sender User 对象
            from pydantic import HttpUrl
            sender_avatar_url = None
            if db_message.sender.avatar_url:
                try:
                    sender_avatar_url = HttpUrl(db_message.sender.avatar_url)
                except:
                    pass
            
            sender = User(
                id=db_message.sender.id,
                name=db_message.sender.name,
                bio=db_message.sender.bio,
                avatar_url=sender_avatar_url,
                created_at=db_message.sender.created_at
            )
            
            return Message(
                id=db_message.id,
                chat_id=db_message.chat.id,
                sender=sender,
                content=db_message.content,
                type=db_message.type,
                ref=ref,
                mentions=mentions_uuids,
                timestamp=db_message.timestamp
            )
        except DoesNotExist:
            raise ValueError(f"Message with id {message_id} not found")

    async def store_message(self, message: MessageCreate, sender_id: UUID) -> Message:
        """存储消息"""
        try:
            chat = ChatTable.get(ChatTable.id == message.chat_id)
            sender = UserTable.get(UserTable.id == sender_id)
            
            # 处理 mentions
            mentions_json = json.dumps([str(uid) for uid in message.mentions]) if message.mentions else None
            
            # 处理 ref
            ref_json = None
            if message.ref:
                ref_json = json.dumps({
                    "message_id": str(message.ref.message_id),
                    "content": message.ref.content,
                    "sender_name": message.ref.sender_name,
                    "timestamp": message.ref.timestamp.isoformat()
                })
            
            db_message = MessageTable.create(
                chat=chat,
                sender=sender,
                content=message.content,
                type=message.type,
                ref_data=ref_json,
                mentions=mentions_json
            )
            
            # 解析 mentions
            mentions_list = json.loads(db_message.mentions) if db_message.mentions else []
            mentions_uuids = [UUID(uid) for uid in mentions_list]
            
            # 构造完整的 sender User 对象
            from pydantic import HttpUrl
            sender_avatar_url = None
            if sender.avatar_url:
                try:
                    sender_avatar_url = HttpUrl(sender.avatar_url)
                except:
                    pass
            
            sender_user = User(
                id=sender.id,
                name=sender.name,
                bio=sender.bio,
                avatar_url=sender_avatar_url,
                created_at=sender.created_at
            )
            
            return Message(
                id=db_message.id,
                chat_id=db_message.chat.id,
                sender=sender_user,
                content=db_message.content,
                type=db_message.type,
                ref=message.ref,
                mentions=mentions_uuids,
                timestamp=db_message.timestamp
            )
        except DoesNotExist:
            raise ValueError("Chat or sender not found")

    async def get_chats_for_user(self, user_id: UUID) -> List[Chat]:
        """获取用户的聊天列表"""
        try:
            user = UserTable.get(UserTable.id == user_id)
            chat_members = ChatMemberTable.select().where(ChatMemberTable.user == user)
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
            user = UserTable.get(UserTable.id == requester_id)
            member_relation = ChatMemberTable.get_or_none(
                (ChatMemberTable.chat == chat) & 
                (ChatMemberTable.user == user)
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

    async def get_chat_members(self, chat_id: UUID) -> List[User]:
        """获取聊天成员列表 - 简洁版本"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            chat_members = ChatMemberTable.select().where(ChatMemberTable.chat == chat)
            users = []
            for member in chat_members:
                user = member.user
                
                # 处理avatar_url
                from pydantic import HttpUrl
                avatar_url = None
                if user.avatar_url:
                    try:
                        avatar_url = HttpUrl(user.avatar_url)
                    except:
                        avatar_url = None
                
                users.append(User(
                    id=user.id,
                    created_at=user.created_at,
                    name=user.name,
                    avatar_url=avatar_url,
                    bio=user.bio
                ))
            return users
        except DoesNotExist:
            return []
    
    async def get_chat_member_ids(self, chat_id: UUID) -> List[UUID]:
        """获取聊天成员ID列表（用于Redis消息推送）"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            chat_members = ChatMemberTable.select().where(ChatMemberTable.chat == chat)
            return [member.user.id for member in chat_members]
        except DoesNotExist:
            return []

    async def leave_chat(self, chat_id: UUID, user_id: UUID) -> bool:
        """退出聊天，如果是创建者退出则自动删除聊天"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            user = UserTable.get(UserTable.id == user_id)
            
            # 检查是否是创建者
            if chat.creator.id == user_id:
                # 创建者退出，删除整个聊天
                return await self.delete_chat(chat_id, user_id)
            else:
                # 普通成员退出
                ChatMemberTable.delete().where(
                    (ChatMemberTable.chat == chat) & 
                    (ChatMemberTable.user == user)
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
                
                # 解析 ref_data
                ref = None
                if db_message.ref_data:
                    try:
                        ref_dict = json.loads(db_message.ref_data)
                        ref = MessageRef(
                            message_id=UUID(ref_dict["message_id"]),
                            content=ref_dict["content"],
                            sender_name=ref_dict["sender_name"],
                            timestamp=datetime.fromisoformat(ref_dict["timestamp"])
                        )
                    except:
                        pass
                
                # 构造完整的 sender User 对象
                from pydantic import HttpUrl
                sender_avatar_url = None
                if db_message.sender.avatar_url:
                    try:
                        sender_avatar_url = HttpUrl(db_message.sender.avatar_url)
                    except:
                        pass
                
                sender = User(
                    id=db_message.sender.id,
                    name=db_message.sender.name,
                    bio=db_message.sender.bio,
                    avatar_url=sender_avatar_url,
                    created_at=db_message.sender.created_at
                )
                
                messages.append(Message(
                    id=db_message.id,
                    chat_id=db_message.chat.id,
                    sender=sender,
                    content=db_message.content,
                    type=db_message.type,
                    ref=ref,
                    mentions=mentions_uuids,
                    timestamp=db_message.timestamp
                ))
            
            return messages
            
        except DoesNotExist:
            return []

    async def remove_member(self, chat_id: UUID, user_id: UUID, requester_id: UUID) -> bool:
        """移除成员，只有创建者才能移除其他人"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            user = UserTable.get(UserTable.id == user_id)
            
            # 检查权限：只有创建者才能踢出成员
            if chat.creator.id != requester_id:
                raise PermissionError("只有创建者才能移除成员")
            
            # 不能移除自己
            if user_id == requester_id:
                raise ValueError("不能移除自己，请使用退出功能")
            
            # 检查成员是否在聊天中
            member_relation = ChatMemberTable.get_or_none(
                (ChatMemberTable.chat == chat) & 
                (ChatMemberTable.user == user)
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

    async def add_member(self, chat_id: UUID, user_id: UUID, requester_id: UUID) -> bool:
        """添加成员，只有创建者才能添加其他人"""
        try:
            chat = ChatTable.get(ChatTable.id == chat_id)
            user = UserTable.get(UserTable.id == user_id)
            
            # 检查权限：只有创建者才能邀请成员
            if chat.creator.id != requester_id:
                raise PermissionError("只有创建者才能添加成员")
            
            # 检查成员是否已经在聊天中
            existing_member = ChatMemberTable.get_or_none(
                (ChatMemberTable.chat == chat) & 
                (ChatMemberTable.user == user)
            )
            
            if existing_member:
                return False  # 成员已经在聊天中
            
            # 添加成员
            ChatMemberTable.create(chat=chat, user=user)
            return True
            
        except DoesNotExist:
            return False
        except PermissionError:
            raise

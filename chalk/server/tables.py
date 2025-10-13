"""
数据库表定义
职责：直接映射数据库表结构，使用Peewee ORM
命名规范：所有数据库表模型以Table后缀命名，避免与业务模型混淆
"""
import uuid
from datetime import datetime

from peewee import *

from .config import get_settings

# 获取配置
settings = get_settings()

# SQLite 数据库配置（使用配置管理）
db = SqliteDatabase(settings.sqlite_path)

class BaseTable(Model):
    """数据库表基类"""
    class Meta:
        database = db

class AgentTable(BaseTable):
    """代理数据表 - 最简洁的微信账号设计"""
    # 基本标识信息
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField(max_length=100, unique=True)
    
    # 档案信息
    avatar_url = CharField(max_length=500, null=True)
    bio = TextField()  # 个人简介和能力说明
    
    # 时间戳
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'agents'

class ChatTable(BaseTable):
    """聊天数据表"""
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    type = CharField(max_length=10)  # 'group' or 'private'
    name = CharField(max_length=255, null=True)
    creator = ForeignKeyField(AgentTable, backref='created_chats')  # 创建者
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'chats'

class ChatMemberTable(BaseTable):
    """聊天成员关系表"""
    chat = ForeignKeyField(ChatTable, backref='members')
    agent = ForeignKeyField(AgentTable, backref='chats')
    joined_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'chat_members'
        primary_key = CompositeKey('chat', 'agent')

class MessageTable(BaseTable):
    """消息数据表"""
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    chat = ForeignKeyField(ChatTable, backref='messages')
    sender = ForeignKeyField(AgentTable, backref='sent_messages')
    content = TextField()
    type = CharField(max_length=20, default='text')
    parent = ForeignKeyField('self', null=True, backref='replies')
    mentions = TextField(null=True)  # JSON string of UUIDs
    timestamp = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'messages'

def get_all_tables():
    """获取所有表模型列表"""
    return [AgentTable, ChatTable, ChatMemberTable, MessageTable]


def get_database():
    """获取数据库连接"""
    return db
"""User - 纯数据类"""
from datetime import datetime
from uuid import UUID


class User:
    """用户对象 - 纯数据，零行为"""
    
    def __init__(self, id: UUID, name: str, bio: str = "", avatar_url: str = None, created_at: datetime = None):
        self.id = id
        self.name = name
        self.bio = bio
        self.avatar_url = avatar_url
        self.created_at = created_at or datetime.now()
    
    def __repr__(self):
        return f"User(name='{self.name}')"
    
    def __eq__(self, other):
        return isinstance(other, User) and self.id == other.id
    
    def __hash__(self):
        return hash(self.id)

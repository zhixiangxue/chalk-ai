"""
智能体对象

包含智能体的数据和行为
"""
from typing import List, Optional, TYPE_CHECKING
import httpx
from uuid import UUID
from datetime import datetime

if TYPE_CHECKING:
    from .chat import Chat
    from .message import Message

# 全局 base_url，由 Client 设置
_global_base_url: Optional[str] = None


def set_base_url(url: str):
    """设置全局 base_url（由 Client 调用）"""
    global _global_base_url
    _global_base_url = url


def get_base_url() -> str:
    """获取全局 base_url"""
    if _global_base_url is None:
        return "http://localhost:8000"  # 默认值
    return _global_base_url


class Agent:
    """智能体对象 - 具备完整的行为能力
    
    设计原则：
    1. 简化构造函数，只接受必要参数
    2. Agent操作Chat，而不Chat依赖Agent
    3. 提供 join_chat、leave_chat 等方法
    4. 提供通过类方法创建或从ID恢复
    """
    
    def __init__(self, id: UUID, name: str, bio: str = "", avatar_url: str = None, created_at: datetime = None):
        """简化的Agent构造函数 - 支持更多参数"""
        self.id = id
        self.name = name
        self.bio = bio
        self.avatar_url = avatar_url
        self.created_at = created_at or datetime.now()
    
    @property
    def base_url(self) -> str:
        """获取 base_url"""
        return get_base_url()
    
    @classmethod
    async def create(cls, name: str, bio: str = "", avatar_url: str = None) -> 'Agent':
        """创建新智能体 - 使用全局配置并支持完整参数"""
        data = {
            "name": name,
            "bio": bio
        }
        if avatar_url:
            data["avatar_url"] = avatar_url
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{get_base_url()}/agents", json=data)
            
            if response.status_code == 409:
                raise ValueError(response.json().get('detail', f'用户名 "{name}" 已存在'))
            elif response.status_code != 200:
                raise ValueError(f"创建智能体失败: {response.text}")
            
            agent_data = response.json()
        
        return cls(
            id=UUID(agent_data["id"]),
            name=agent_data["name"],
            bio=agent_data.get("bio", ""),
            avatar_url=agent_data.get("avatar_url"),
            created_at=datetime.fromisoformat(agent_data["created_at"])
        )
    
    @classmethod
    async def from_id(cls, agent_id: UUID) -> 'Agent':
        """从ID恢复智能体 - 使用全局配置并返回完整信息"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{get_base_url()}/agents/{agent_id}")
            
            if response.status_code != 200:
                raise ValueError(f"智能体 {agent_id} 不存在")
            
            agent_data = response.json()
        
        return cls(
            id=UUID(agent_data["id"]),
            name=agent_data["name"],
            bio=agent_data.get("bio", ""),
            avatar_url=agent_data.get("avatar_url"),
            created_at=datetime.fromisoformat(agent_data["created_at"])
        )
    
    async def join_chat(self, chat: 'Chat'):
        """加入聊天 - Agent操作Chat是更自然的设计"""
        headers = {"X-Agent-ID": str(self.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/chats/{chat.id}/join", headers=headers)
            response.raise_for_status()
        
        return response.json()
    
    async def leave_chat(self, chat: 'Chat'):
        """离开聊天"""
        headers = {"X-Agent-ID": str(self.id)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/chats/{chat.id}/leave", headers=headers)
            response.raise_for_status()
        
        return response.json()
    
    async def list_chats(self) -> List['Chat']:
        """获取此Agent参与的所有聊天（自动绑定当前Agent）"""
        async with httpx.AsyncClient() as client:
            headers = {"X-Agent-ID": str(self.id)}
            response = await client.get(f"{self.base_url}/chats", headers=headers)
            response.raise_for_status()
            chats_data = response.json()
        
        from .chat import Chat
        
        # 为每个chat创建Chat对象，需要先获取创建者Agent
        chat_objects = []
        for chat in chats_data:
            # 获取创建者Agent
            creator = await Agent.from_id(UUID(chat["creator_id"]))
            
            chat_obj = Chat(
                id=UUID(chat["id"]),
                name=chat["name"],
                type=chat.get("type", "group"),
                created_at=datetime.fromisoformat(chat["created_at"]),
                operator=self,  # 当前Agent作为操作者
                creator=creator  # 聊天的创建者
            )
            chat_objects.append(chat_obj)
        
        return chat_objects
    
    async def info(self) -> dict:
        """获取Agent的详细信息"""
        return {
            "id": str(self.id),
            "name": self.name,
            "bio": self.bio,
            "avatar_url": str(self.avatar_url) if self.avatar_url else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def __eq__(self, other):
        if not isinstance(other, Agent):
            return False
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)
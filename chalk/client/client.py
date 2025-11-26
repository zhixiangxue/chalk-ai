"""Client - 核心客户端"""
import asyncio
import json
from datetime import datetime
from typing import Optional, List, Callable, Union
from uuid import UUID
import httpx
import websockets

from .user import User
from .chat import Chat
from .message import Message, MessageRef
from .logger import get_logger

logger = get_logger("Client")


class Client:
    """Chalk AI 客户端 - 代表"我"
    
    使用示例:
        alice = Client("alice", "password123")
        bob = Client("bob", "password456")
        
        @alice.on("message")
        async def handle(msg):
            await msg.reply("收到!")
        
        # 第一次调用API时自动连接
        chat = await alice.create_chat("群聊")
    """
    
    def __init__(self, name: str, password: str, bio: str = "", endpoint: str = "localhost:8000"):
        """初始化
        
        Args:
            name: 用户名
            password: 密码
            bio: 简介
            endpoint: 服务器地址
        """
        self.name = name
        self.password = password
        self.bio = bio
        
        # 解析endpoint
        if not endpoint.startswith("http"):
            endpoint = "http://" + endpoint
        self.http_url = endpoint.replace("ws://", "http://").replace("wss://", "https://")
        self.ws_url = self.http_url.replace("http://", "ws://").replace("https://", "wss://")
        
        # 我的信息
        self.me: Optional[User] = None
        
        # 连接状态
        self._http: Optional[httpx.AsyncClient] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._started = False
        
        # 事件处理
        self._handlers = []
    
    async def _ensure_started(self):
        """确保客户端已启动（懒加载）"""
        if not self._started:
            await self._start()
    
    async def _start(self):
        """启动客户端"""
        if self._started:
            return
        
        try:
            # HTTP客户端
            self._http = httpx.AsyncClient(base_url=self.http_url, timeout=30.0)
            
            # 登录或注册
            resp = await self._http.post("/auth/login", json={"name": self.name, "password": self.password})
            
            if resp.status_code == 404:
                # 注册
                resp = await self._http.post("/auth/register", json={
                    "name": self.name,
                    "password": self.password,
                    "bio": self.bio
                })
            
            if resp.status_code != 200:
                raise Exception(f"认证失败: {resp.text}")
            
            data = resp.json()
            self.me = User(
                id=UUID(data["id"]),
                name=data["name"],
                bio=data.get("bio", ""),
                avatar_url=data.get("avatar_url"),
                created_at=datetime.fromisoformat(data["created_at"])
            )
            
            logger.success(f"✅ 登录成功: {self.me.name}")
            
            # WebSocket
            self._ws = await websockets.connect(f"{self.ws_url}/ws/{self.me.id}")
            self._running = True
            self._started = True
            
            # 启动消息监听
            asyncio.create_task(self._listen())
            
        except Exception as e:
            logger.error(f"❌ 启动失败: {e}")
            raise
    
    async def stop(self):
        """停止客户端"""
        self._running = False
        
        if self._ws:
            await self._ws.close()
        
        if self._http:
            await self._http.aclose()
    
    async def _listen(self):
        """监听WebSocket消息"""
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                
                if data.get("type") == "server_message":
                    msg_data = data["message"]
                    
                    # 解析sender
                    sender_data = msg_data["sender"]
                    sender = User(
                        id=UUID(sender_data["id"]),
                        name=sender_data["name"],
                        bio=sender_data.get("bio", ""),
                        avatar_url=sender_data.get("avatar_url"),
                        created_at=datetime.fromisoformat(sender_data["created_at"])
                    )
                    
                    # 解析ref
                    ref = MessageRef.from_dict(msg_data["ref"]) if msg_data.get("ref") else None
                    
                    # 创建Message
                    msg = Message(
                        id=UUID(msg_data["id"]),
                        chat_id=UUID(msg_data["chat_id"]),
                        sender=sender,
                        content=msg_data["content"],
                        mentions=[UUID(m) for m in msg_data.get("mentions", [])],
                        ref=ref,
                        timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                        client=self
                    )
                    
                    # 触发处理器
                    for handler in self._handlers:
                        try:
                            await handler(msg)
                        except Exception as e:
                            logger.error(f"处理器错误: {e}")
        
        except Exception as e:
            if self._running:
                logger.error(f"监听错误: {e}")
    
    def on(self, event: str):
        """注册事件处理器
        
        @client.on("message")
        async def handle(msg):
            ...
        """
        def decorator(func):
            if event == "message":
                self._handlers.append(func)
            return func
        return decorator
    
    # ========== API方法 ==========
    
    async def create_chat(self, name: str, members: List[str] = None) -> Chat:
        """创建群聊（已废弃，请使用 create_group_chat）"""
        return await self.create_group_chat(name, members)
    
    async def create_group_chat(self, name: str, members: List[str] = None) -> Chat:
        """创建群聊"""
        await self._ensure_started()
        resp = await self._http.post("/chats", json={
            "name": name,
            "type": "group",
            "members": members or []
        }, headers={"X-User-ID": str(self.me.id)})
        
        resp.raise_for_status()
        data = resp.json()
        
        return Chat(
            id=UUID(data["id"]),
            name=data["name"],
            type=data.get("type", "group"),
            creator=self.me,
            created_at=datetime.fromisoformat(data["created_at"]),
            client=self
        )
    
    async def create_direct_chat(self, user_id: Union[str, UUID]) -> Chat:
        """创建私聊（1对1）
        
        Args:
            user_id: 对方用户ID
        
        Returns:
            Chat对象（私聊）
        """
        await self._ensure_started()
        
        # 转换为UUID
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        
        # 生成私聊名称（顺序无关）
        ids = sorted([str(self.me.id), str(user_id)])
        direct_name = f"direct:{ids[0]}:{ids[1]}"
        
        # 查找是否已存在
        chats = await self.list_chats()
        for chat in chats:
            if chat.name == direct_name:
                return chat
        
        # 不存在就创建
        resp = await self._http.post("/chats", json={
            "name": direct_name,
            "type": "direct",
            "members": [str(user_id)]
        }, headers={"X-User-ID": str(self.me.id)})
        
        resp.raise_for_status()
        data = resp.json()
        
        return Chat(
            id=UUID(data["id"]),
            name=data["name"],
            type="direct",
            creator=self.me,
            created_at=datetime.fromisoformat(data["created_at"]),
            client=self
        )
    
    async def list_chats(self) -> List[Chat]:
        """列出所有聊天（群聊+私聊）"""
        await self._ensure_started()
        resp = await self._http.get("/chats", headers={"X-User-ID": str(self.me.id)})
        resp.raise_for_status()
        
        chats = []
        for data in resp.json():
            creator = await self._get_user(UUID(data["creator_id"]))
            chats.append(Chat(
                id=UUID(data["id"]),
                name=data["name"],
                type=data.get("type", "group"),
                creator=creator,
                created_at=datetime.fromisoformat(data["created_at"]),
                client=self
            ))
        
        return chats
    
    async def get_chat(self, chat_id: UUID) -> Chat:
        """获取聊天详情"""
        await self._ensure_started()
        resp = await self._http.get(f"/chats/{chat_id}", headers={"X-User-ID": str(self.me.id)})
        resp.raise_for_status()
        data = resp.json()
        
        creator = await self._get_user(UUID(data["creator_id"]))
        
        return Chat(
            id=UUID(data["id"]),
            name=data["name"],
            type=data.get("type", "group"),
            creator=creator,
            created_at=datetime.fromisoformat(data["created_at"]),
            client=self
        )
    
    async def join_chat(self, chat_id: UUID):
        """加入聊天"""
        await self._ensure_started()
        resp = await self._http.post(f"/chats/{chat_id}/join", headers={"X-User-ID": str(self.me.id)})
        resp.raise_for_status()
    
    async def send_message(self, chat_id: UUID, content: str, ref: Optional[MessageRef] = None) -> Message:
        """发送消息"""
        await self._ensure_started()
        payload = {
            "type": "client_message",
            "data": {
                "chat_id": str(chat_id),
                "content": content,
                "type": "text",
                "mentions": []
            }
        }
        
        if ref:
            payload["data"]["ref"] = ref.to_dict()
        
        # 通过WebSocket发送
        await self._ws.send(json.dumps(payload))
        
        # 返回一个临时Message（实际Message会通过WebSocket推送）
        return Message(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            chat_id=chat_id,
            sender=self.me,
            content=content,
            mentions=[],
            ref=ref,
            timestamp=datetime.now(),
            client=self
        )
    
    async def get_messages(self, chat_id: UUID, limit: int = 50) -> List[Message]:
        """获取消息列表"""
        await self._ensure_started()
        resp = await self._http.get(f"/chats/{chat_id}/messages", params={"limit": limit, "offset": 0})
        resp.raise_for_status()
        
        messages = []
        for data in resp.json():
            # 解析sender
            sender_data = data["sender"]
            sender = User(
                id=UUID(sender_data["id"]),
                name=sender_data["name"],
                bio=sender_data.get("bio", ""),
                avatar_url=sender_data.get("avatar_url"),
                created_at=datetime.fromisoformat(sender_data["created_at"])
            )
            
            # 解析ref
            ref = MessageRef.from_dict(data["ref"]) if data.get("ref") else None
            
            messages.append(Message(
                id=UUID(data["id"]),
                chat_id=chat_id,
                sender=sender,
                content=data["content"],
                mentions=[UUID(m) for m in data.get("mentions", [])],
                ref=ref,
                timestamp=datetime.fromisoformat(data["timestamp"]),
                client=self
            ))
        
        return messages
    
    async def get_members(self, chat_id: UUID) -> List[User]:
        """获取聊天成员"""
        await self._ensure_started()
        resp = await self._http.get(f"/chats/{chat_id}/members")
        resp.raise_for_status()
        
        return [
            User(
                id=UUID(data["id"]),
                name=data["name"],
                bio=data.get("bio", ""),
                avatar_url=data.get("avatar_url"),
                created_at=datetime.fromisoformat(data["created_at"])
            )
            for data in resp.json()
        ]
    
    async def whois(self, username: str) -> List[User]:
        """根据用户名查询用户信息（可能返回多个同名用户）
        
        Args:
            username: 用户名
        
        Returns:
            User对象列表（用户名可能重复）
        """
        await self._ensure_started()
        resp = await self._http.get(f"/users/by-name/{username}")
        resp.raise_for_status()
        data_list = resp.json()
        
        users = []
        for data in data_list:
            users.append(User(
                id=UUID(data["id"]),
                name=data["name"],
                bio=data.get("bio", ""),
                avatar_url=data.get("avatar_url"),
                created_at=datetime.fromisoformat(data["created_at"])
            ))
        
        return users
    
    async def _get_user(self, user_id: UUID) -> User:
        """内部方法：获取用户信息"""
        resp = await self._http.get(f"/users/{user_id}")
        resp.raise_for_status()
        data = resp.json()
        
        return User(
            id=UUID(data["id"]),
            name=data["name"],
            bio=data.get("bio", ""),
            avatar_url=data.get("avatar_url"),
            created_at=datetime.fromisoformat(data["created_at"])
        )
    
    async def __aenter__(self):
        await self._ensure_started()
        return self
    
    async def __aexit__(self, *args):
        await self.stop()

"""
Chalk AI 客户端

提供简洁直观的 API 接口，让开发者像使用微信一样接入聊天服务

核心设计理念:
1. 构造简单 - 只需 agent_id 和 endpoint
2. 自动登录 - 不存在则创建，存在则获取信息
3. 事件驱动 - 通过装饰器处理各类消息
4. API 直观 - 支持 chat.send(), message.reply() 等自然调用
"""
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Callable, List, Union
from uuid import UUID
import websockets
import httpx

from .agent import Agent
from .chat import Chat
from .message import Message
from .logger import get_logger

# 初始化日志器
logger = get_logger("ChalkClient")


class Client:
    """
    Chalk AI 聊天客户端
    
    用法示例:
        # 创建客户端
        client = Client(endpoint="localhost:8000")
        
        # 连接服务器（使用已有 Agent）
        success = await client.connect(agent_id="xxxxx")
        
        # 或者创建新 Agent 并连接
        success = await client.connect(name="我的用户名", bio="简介")
        
        # 注册消息处理器
        @client.on("message")
        async def my_handler(message):
            print(f"收到消息: {message.content}")
            chat = await message.get_chat()
            sender = await message.get_sender()
            await chat.send("你好!")
        
        # 列出所有聊天
        chats = await client.list_chats()
        
        # 创建聊天
        chat = await client.create_chat(name="我的群聊")
        
        # 发送消息
        await chat.send("Hello, World!")
    """

    def __init__(self, endpoint: str = "localhost:8000"):
        """
        初始化客户端
        
        Args:
            endpoint: 服务器地址，支持以下格式：
                - "localhost:8000"
                - "http://localhost:8000"
                - "ws://localhost:8000"
                - "example.com:8000"
        """
        # 解析 endpoint，提取 host 和 port
        from urllib.parse import urlparse

        endpoint = endpoint.strip()

        # 如果没有协议，添加默认协议以便解析
        if not endpoint.startswith(('http://', 'https://', 'ws://', 'wss://')):
            endpoint = 'http://' + endpoint

        # 解析 URL
        parsed = urlparse(endpoint)

        # 提取 host 和 port
        host = parsed.hostname or 'localhost'
        port = parsed.port or 8000

        # 构建标准化的 endpoint（不含协议）
        self.endpoint = f"{host}:{port}"

        # 构建完整的 URL
        self.http_url = f"http://{self.endpoint}"
        self.ws_url = f"ws://{self.endpoint}"

        # Agent 对象
        self.agent: Optional[Agent] = None
        self.agent_id: Optional[str] = None

        # WebSocket 连接
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._listen_task: Optional[asyncio.Task] = None

        # 简单重连配置
        self._auto_reconnect = True

        # 连接参数，用于重连
        self._last_agent_id: Optional[str] = None
        self._last_name: Optional[str] = None
        self._last_bio: str = ""

        # 事件处理器
        self._message_handlers: List[Callable] = []
        self._notification_handlers: List[Callable] = []

        # HTTP 客户端
        self._http_client: Optional[httpx.AsyncClient] = None

    async def connect(self, agent_id: Optional[str] = None, name: Optional[str] = None, bio: str = "",
                      auto_reconnect: bool = True) -> bool:
        """
        连接到服务器
        
        支持两种连接方式：
        1. 使用已有 Agent: connect(agent_id="xxxxx")
        2. 创建新 Agent: connect(name="用户名", bio="简介")
        
        Args:
            agent_id: 已有的 Agent ID
            name: 创建新 Agent 的名称
            bio: 创建新 Agent 的简介
            auto_reconnect: 是否启用自动重连
        
        Returns:
            是否连接成功
        """
        # 记录连接参数用于重连
        self._last_agent_id = agent_id
        self._last_name = name
        self._last_bio = bio
        self._auto_reconnect = auto_reconnect

        try:
            # 验证参数
            if not agent_id and not name and not self.agent:
                raise ValueError("必须提供 agent_id 或 name 参数")

            # 创建 HTTP 客户端
            self._http_client = httpx.AsyncClient(base_url=self.http_url, timeout=30.0)

            # 设置全局 base_url
            from .agent import set_base_url
            set_base_url(self.http_url)

            # 登录或注册
            if self.agent and self.agent.id:
                # 重连时使用已有的 Agent ID
                self.agent = await Agent.from_id(self.agent.id)
                self.agent_id = str(self.agent.id)
                logger.info(f"🔄 重连使用已有 Agent: {self.agent.name} ({self.agent.id})")
            elif agent_id:
                # 使用指定的 Agent ID
                self.agent = await Agent.from_id(UUID(agent_id))
                self.agent_id = str(self.agent.id)
                logger.success(f"✅ 已登录: {self.agent.name} ({self.agent.id})")
            else:
                # 创建新 Agent
                self.agent = await Agent.create(name=name, bio=bio)
                self.agent_id = str(self.agent.id)
                logger.success(f"✅ 已创建并登录: {self.agent.name} ({self.agent.id})")

            # 建立 WebSocket 连接
            ws_url = f"{self.ws_url}/ws/{self.agent_id}"
            self._websocket = await websockets.connect(ws_url)
            self._connected = True
            logger.success(f"✅ WebSocket 已连接: {ws_url}")

            # 启动监听任务
            if not self._listen_task or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen_messages())

            return True

        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接，释放资源"""
        self._auto_reconnect = False
        self._connected = False

        # 取消监听任务
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        # 关闭 WebSocket
        if self._websocket:
            try:
                await self._websocket.close()
            except:
                pass
            self._websocket = None

        # 关闭 HTTP 客户端
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        logger.info("🔌 已断开连接")

    async def _listen_messages(self):
        """监听 WebSocket 消息，带自动重连功能"""
        while self._auto_reconnect and self._connected:
            try:
                if not self._websocket:
                    break

                async for message in self._websocket:
                    try:
                        data = json.loads(message)
                        await self._handle_message(data)
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ 收到无效JSON: {message}")

            except websockets.exceptions.ConnectionClosed:
                logger.info("🔌 WebSocket 连接已关闭")
                break

            except asyncio.CancelledError:
                logger.debug("🔌 监听任务已取消")
                break

            except Exception as e:
                logger.error(f"❌ 监听消息出错: {e}")
                break

        # 连接断开，尝试重连
        if self._auto_reconnect:
            while self._auto_reconnect:
                await asyncio.sleep(5)  # 等待5秒后重连
                logger.info("🔄 尝试重连...")
                
                # 先断开
                await self.disconnect()
                
                # 重新连接
                success = await self.connect(
                    agent_id=self._last_agent_id,
                    name=self._last_name, 
                    bio=self._last_bio,
                    auto_reconnect=True
                )
                
                if success:
                    logger.success("✅ 重连成功！")
                    break
                else:
                    logger.warning("❌ 重连失败，5秒后重试...")

    @property
    def is_connected(self) -> bool:
        """返回WebSocket是否已连接"""
        return self._connected

    async def _handle_message(self, data: Dict):
        """处理收到的消息"""
        msg_type = data.get("type", "unknown")

        if msg_type == "server_message":
            # 收到聊天消息
            message_data = data.get("message", {})
            message = Message(
                id=UUID(message_data["id"]),
                chat_id=UUID(message_data["chat_id"]),
                sender_id=UUID(message_data["sender_id"]),
                content=message_data["content"],
                type=message_data.get("type", "text"),
                mentions=[UUID(m) for m in message_data.get("mentions", [])],
                parent_id=UUID(message_data["parent_id"]) if message_data.get("parent_id") else None,
                created_at=datetime.fromisoformat(message_data["timestamp"])
            )

            # 绑定client引用
            message.bind_client(self)

            # 触发消息处理器
            for handler in self._message_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    logger.error(f"⚠️ 消息处理器错误: {e}")

        elif msg_type == "server_connected":
            logger.success(f"🎉 服务器确认连接")

        elif msg_type == "server_ack":
            # 消息发送确认
            pass

        elif msg_type == "server_error":
            error_msg = data.get("message", "")
            logger.error(f"❌ 服务器错误: {error_msg}")

        elif msg_type == "notification":
            # 系统通知（暂未实现）
            for handler in self._notification_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"⚠️ 通知处理器错误: {e}")

    def on(self, event: str):
        """
        事件装饰器
        
        支持的事件:
        - "message": 收到消息
        - "notification": 收到系统通知
        
        用法:
            @client.on("message")
            async def handle_message(message):
                print(f"收到消息: {message.content}")
        """

        def decorator(func: Callable):
            if event == "message":
                self._message_handlers.append(func)
            elif event == "notification":
                self._notification_handlers.append(func)
            else:
                raise ValueError(f"不支持的事件类型: {event}")
            return func

        return decorator

    # ========== Chat 相关操作 ==========

    async def list_chats(self) -> List[Chat]:
        """
        列出我所有的聊天
        
        Returns:
            Chat 对象列表
        """
        if not self.agent:
            raise RuntimeError("请先调用 connect() 连接服务器")

        chats = await self.agent.list_chats()

        # 为每个 chat 注入 client 引用
        for chat in chats:
            chat.client = self

        return chats

    async def create_chat(self, name: str = None, chat_type: str = "group",
                          members: List[Union[Agent, str]] = None) -> Chat:
        """
        创建一个新的聊天
        
        Args:
            name: 聊天名称
            chat_type: 聊天类型 ('group' 或 'private')
            members: 初始成员列表（Agent 对象或 agent_id 字符串）
        
        Returns:
            创建的 Chat 对象
        """
        if not self.agent:
            raise RuntimeError("请先调用 connect() 连接服务器")

        # 转换 members 为 Agent 对象
        member_agents = []
        if members:
            for m in members:
                if isinstance(m, str):
                    member_agents.append(await Agent.from_id(UUID(m)))
                else:
                    member_agents.append(m)

        chat = await Chat.create(name=name or "新聊天", creator=self.agent,
                                 chat_type=chat_type, members=member_agents)

        # 注入 client 引用
        chat.client = self

        return chat

    async def join_chat(self, chat_id: Union[str, UUID]) -> Chat:
        """
        加入别人的聊天
        
        Args:
            chat_id: 聊天 ID
        
        Returns:
            Chat 对象
        """
        if not self.agent:
            raise RuntimeError("请先调用 connect() 连接服务器")

        if isinstance(chat_id, str):
            chat_id = UUID(chat_id)

        # 获取 Chat 对象
        chat = await Chat.from_id(chat_id, self.agent)

        # 加入聊天
        await self.agent.join_chat(chat)

        # 注入 client 引用
        chat.client = self

        return chat

    async def leave_chat(self, chat_id: Union[str, UUID, Chat]):
        """
        退出聊天（如果是创建者退出，则等同于删除）
        
        Args:
            chat_id: 聊天 ID 或 Chat 对象
        """
        if not self.agent:
            raise RuntimeError("请先调用 connect() 连接服务器")

        if isinstance(chat_id, Chat):
            chat = chat_id
        else:
            if isinstance(chat_id, str):
                chat_id = UUID(chat_id)
            chat = await Chat.from_id(chat_id, self.agent)

        await self.agent.leave_chat(chat)

    # ========== Agent 相关操作 ==========

    async def whois(self, agent: Union[str, UUID, Agent]) -> Agent:
        """
        查看别人的信息
        
        Args:
            agent: Agent ID 或 Agent 对象
        
        Returns:
            Agent 对象
        """
        if isinstance(agent, Agent):
            # 刷新信息
            return await Agent.from_id(agent.id)
        elif isinstance(agent, str):
            return await Agent.from_id(UUID(agent))
        else:
            return await Agent.from_id(agent)

    # ========== Chat 信息查询 ==========

    async def whatis(self, chat: Union[str, UUID, Chat]) -> Chat:
        """
        查看聊天的信息
        
        Args:
            chat: Chat ID 或 Chat 对象
        
        Returns:
            Chat 对象
        """
        if not self.agent:
            raise RuntimeError("请先调用 connect() 连接服务器")

        if isinstance(chat, Chat):
            # 刷新信息
            result = await Chat.from_id(chat.id, self.agent)
        elif isinstance(chat, str):
            result = await Chat.from_id(UUID(chat), self.agent)
        else:
            result = await Chat.from_id(chat, self.agent)

        # 注入 client 引用
        result.client = self

        return result

    # ========== Context Manager 支持 ==========

    def with_agent(self, agent_id: Optional[str] = None, name: Optional[str] = None, bio: str = "") -> 'Client':
        """
        配置 Agent 信息用于 async with 语法
        
        用法:
            async with Client("localhost:8000").with_agent(name="用户") as client:
                ...
        
        Args:
            agent_id: 已有的 Agent ID
            name: 创建新 Agent 的名称
            bio: 创建新 Agent 的简介
        """
        self._context_agent_id = agent_id
        self._context_name = name
        self._context_bio = bio
        return self

    async def __aenter__(self):
        """支持 async with 语法"""
        # 使用 with_agent 设置的参数
        agent_id = getattr(self, '_context_agent_id', None)
        name = getattr(self, '_context_name', None)
        bio = getattr(self, '_context_bio', '')

        if not agent_id and not name:
            raise ValueError("使用 async with 时必须先调用 with_agent() 设置 Agent 信息")

        await self.connect(agent_id=agent_id, name=name, bio=bio)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时自动清理资源"""
        await self.disconnect()
        return False

    def __repr__(self):
        status = "connected" if self._connected else "disconnected"
        agent_info = f"{self.agent.name} ({self.agent.id})" if self.agent else "not logged in"
        return f"Client(agent={agent_info}, status={status})"


__all__ = ['Client']

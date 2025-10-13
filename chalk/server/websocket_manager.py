"""
WebSocket 连接管理器

负责管理所有活跃的 WebSocket 连接，维护 agent_id 到 websocket 的映射关系
"""
import json
from typing import Dict, Optional, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from .config import get_settings
from .redis_client import RedisClient
from .logger import get_logger

logger = get_logger("WebSocketManager")


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # agent_id -> WebSocket 的映射
        self.active_connections: Dict[str, WebSocket] = {}
        # 在线用户集合，用于快速查询
        self.online_agents: Set[str] = set()
        
        logger.info("WebSocket 连接管理器已初始化")
    
    async def connect(self, agent_id: str, websocket: WebSocket) -> bool:
        """
        建立 WebSocket 连接
        
        Args:
            agent_id: 智能体ID
            websocket: WebSocket 连接对象
            
        Returns:
            bool: 连接是否建立成功
        """
        try:
            # 接受 WebSocket 连接
            await websocket.accept()
            
            # 如果该 agent 已有连接，关闭旧连接
            if agent_id in self.active_connections:
                logger.info(f"Agent {agent_id} 已存在连接，关闭旧连接")
                await self._close_connection(agent_id)
            
            # 建立新连接
            self.active_connections[agent_id] = websocket
            self.online_agents.add(agent_id)
            
            # 可选：将在线状态同步到 Redis，供其他服务查询
            settings = get_settings()
            redis_client = RedisClient(settings.redis_url)
            await redis_client.connect()
            try:
                await redis_client.set_agent_online(agent_id)
            finally:
                await redis_client.disconnect()
            
            logger.info(f"Agent {agent_id} WebSocket 连接已建立")
            return True
            
        except Exception as e:
            logger.error(f"建立 WebSocket 连接失败 {agent_id}: {str(e)}")
            return False
    
    async def disconnect(self, agent_id: str):
        """
        断开 WebSocket 连接
        
        Args:
            agent_id: 智能体ID
        """
        if agent_id in self.active_connections:
            await self._close_connection(agent_id)
            logger.info(f"Agent {agent_id} WebSocket 连接已断开")
    
    async def _close_connection(self, agent_id: str):
        """
        内部方法：关闭指定的连接
        
        Args:
            agent_id: 智能体ID
        """
        try:
            # 关闭 WebSocket 连接
            websocket = self.active_connections[agent_id]
            await websocket.close()
        except Exception as e:
            logger.warning(f"关闭 WebSocket 连接时出错 {agent_id}: {str(e)}")
        finally:
            # 清理连接记录
            self.active_connections.pop(agent_id, None)
            self.online_agents.discard(agent_id)
            
            # 清理 Redis 中的在线状态
            try:
                settings = get_settings()
                redis_client = RedisClient(settings.redis_url)
                await redis_client.connect()
                try:
                    await redis_client.set_agent_offline(agent_id)
                finally:
                    await redis_client.disconnect()
            except Exception as e:
                logger.warning(f"清理 Redis 在线状态失败 {agent_id}: {str(e)}")
    
    async def send_outbound_message(self, agent_id: str, message) -> bool:
        """
        向指定 agent 发送 WebSocket 出站消息模型（类型安全）
        
        Args:
            agent_id: 目标智能体ID
            message: WSOutboundMessage 模型实例
            
        Returns:
            bool: 消息是否发送成功
        """
        from .models import WSOutboundMessage
        
        # 类型检查
        if not isinstance(message, WSOutboundMessage):
            raise TypeError(f"Message must be WSOutboundMessage, got {type(message)}")
        
        if agent_id not in self.active_connections:
            logger.debug(f"Agent {agent_id} 不在线，无法发送消息")
            return False
        
        try:
            websocket = self.active_connections[agent_id]
            message_json = message.model_dump_json()
            await websocket.send_text(message_json)
            logger.debug(f"Outbound消息已发送给 Agent {agent_id}: {message.type}")
            return True
            
        except WebSocketDisconnect:
            logger.info(f"Agent {agent_id} 已断开连接，移除连接记录")
            await self.disconnect(agent_id)
            return False
        except Exception as e:
            logger.error(f"发送Outbound消息失败 {agent_id}: {str(e)}")
            # 连接可能已断开，尝试清理
            await self.disconnect(agent_id)
            return False

# 全局连接管理器实例
connection_manager = ConnectionManager()
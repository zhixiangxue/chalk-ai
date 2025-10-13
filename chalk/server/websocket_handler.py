"""
WebSocket 处理器

负责处理 WebSocket 连接、消息收发、Redis 订阅等逻辑
"""
import json
import asyncio
from uuid import UUID
from typing import Dict, Any

from fastapi import WebSocket, WebSocketDisconnect

from .config import get_settings
from .database import Database
from .models import (
    Message,
    WSMessageFactory, WSInboundMessage,
    ServerConnectedMessage, ServerPongMessage, ServerErrorMessage, 
    ServerAckMessage, ServerGeneralMessage,
    ClientGeneralMessage, ClientPingMessage
)
from .redis_client import RedisClient
from .redis_channels import RedisChannels
from .websocket_manager import connection_manager
from .tasks import distribute_message
from .logger import get_logger

logger = get_logger("WebSocketHandler")


class WebSocketHandler:
    """WebSocket 消息处理器"""
    
    def __init__(self):
        self.settings = get_settings()
        self.active_subscribers: Dict[str, asyncio.Task] = {}  # agent_id -> subscriber_task
    
    async def handle_connection(self, websocket: WebSocket, agent_id: str):
        """
        处理 WebSocket 连接的完整生命周期
        
        Args:
            websocket: WebSocket 连接对象
            agent_id: 智能体ID
        """
        # 验证 agent_id 的有效性
        if not await self._validate_agent(agent_id):
            logger.warning(f"无效的 agent_id: {agent_id}")
            await websocket.close(code=4001, reason="Invalid agent_id")
            return
        
        # 建立连接
        if not await connection_manager.connect(agent_id, websocket):
            logger.error(f"无法建立 WebSocket 连接: {agent_id}")
            return
        
        try:
            # 发送连接确认消息
            await self._send_connection_ack(agent_id)
            
            # 补偿推送离线期间的消息
            await self._handle_offline_messages(agent_id)
            
            # 启动即时消息推送任务
            instant_message_task = asyncio.create_task(
                self._handle_instant_messages(agent_id)
            )
            self.active_subscribers[agent_id] = instant_message_task
            
            # 启动心跳任务定期刷新在线状态
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(agent_id)
            )
            
            try:
                # 启动客户端消息接收循环
                await self._handle_client_messages(websocket, agent_id)
            finally:
                # 取消心跳任务
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
        except WebSocketDisconnect:
            logger.info(f"Agent {agent_id} WebSocket 连接断开")
        except Exception as e:
            logger.error(f"WebSocket 处理出错 {agent_id}: {str(e)}", exc_info=True)
        finally:
            # 清理资源
            await self._cleanup_connection(agent_id)
    
    async def _validate_agent(self, agent_id: str) -> bool:
        """
        验证 agent_id 是否有效
        
        Args:
            agent_id: 智能体ID
            
        Returns:
            bool: 是否有效
        """
        try:
            # 连接数据库验证
            db = Database()
            await db.connect()
            try:
                await db.get_agent(UUID(agent_id))
                return True
            except (ValueError, TypeError):
                return False
            finally:
                await db.disconnect()
        except Exception as e:
            logger.error(f"验证 agent_id 失败: {str(e)}")
            return False
    
    async def _send_connection_ack(self, agent_id: str):
        """
        发送连接确认消息
        
        Args:
            agent_id: 智能体ID
        """
        ack_message = ServerConnectedMessage(agent_id=agent_id)
        
        await connection_manager.send_outbound_message(agent_id, ack_message)
        logger.debug(f"连接确认消息已发送: {agent_id}")
    
    async def _heartbeat_loop(self, agent_id: str):
        """
        心跳循环，定期刷新Agent在线状态
        
        Args:
            agent_id: 智能体ID
        """
        redis_client = RedisClient(self.settings.redis_url)
        
        try:
            await redis_client.connect()
            
            while True:
                try:
                    # 每30秒刷新一次在线状态
                    await asyncio.sleep(30)
                    await redis_client.set_agent_online(agent_id)
                    logger.debug(f"已刷新 {agent_id} 在线状态")
                    
                except asyncio.CancelledError:
                    logger.debug(f"Agent {agent_id} 心跳任务已取消")
                    break
                except Exception as e:
                    logger.warning(f"刷新在线状态失败 {agent_id}: {str(e)}")
                    await asyncio.sleep(30)  # 出错后等待再试
                    
        finally:
            await redis_client.disconnect()
            
    async def _handle_offline_messages(self, agent_id: str):
        """
        补偿推送离线期间的消息
        
        当 Agent 重新连接时，补偿之前未实时推送的离线消息
        现在使用统一的 message_id 格式，与 instant 消息处理流程一致
        
        Args:
            agent_id: 智能体ID
        """
        try:
            redis_client = RedisClient(self.settings.redis_url)
            
            await redis_client.connect()
            
            try:
                # 获取离线消息 ID 列表（现在格式与 instant 一致）
                offline_messages = await redis_client.get_offline_message_ids(agent_id)
                
                if offline_messages:
                    logger.info(f"为 {agent_id} 发送 {len(offline_messages)} 条离线消息")
                    
                    # 使用统一的发送方法处理
                    for msg_data in offline_messages:
                        message_id = msg_data.get("message_id")
                        if message_id:
                            # 获取消息并发送
                            message = await self._get_message_by_id(message_id)
                            ws_message = ServerGeneralMessage(message=message)
                            await connection_manager.send_outbound_message(agent_id, ws_message)
                    
                    # 清理已发送的离线消息
                    await redis_client.clear_offline_message_ids(agent_id)
                
            finally:
                await redis_client.disconnect()
                
        except Exception as e:
            logger.error(f"发送离线消息失败 {agent_id}: {str(e)}")
    
    async def _handle_instant_messages(self, agent_id: str):
        """
        处理即时消息推送任务
        
        这是一个后台任务，专门负责接收 Huey 处理后的即时消息
        并通过 WebSocket 立即推送给在线的 Agent
        
        Args:
            agent_id: 智能体ID
        """
        redis_client = RedisClient(self.settings.redis_url)
        
        try:
            await redis_client.connect()
            
            # 订阅该 agent 的即时消息频道和通知频道
            channels = [
                RedisChannels.agent_inbox_instant(agent_id),
                RedisChannels.agent_notifications(agent_id)
            ]
            
            await redis_client.subscribe_channels(channels)
            logger.info(f"开始订阅即时消息频道: {channels}")
            
            # 监听即时消息 - 这是一个无限循环，会一直运行
            async for message in redis_client.listen():
                if message["type"] == "message":
                    try:
                        # 解析消息数据（现在是 message_id 格式）
                        message_data = json.loads(message["data"])
                        message_id = message_data.get("message_id")
                        
                        if message_id:
                            # 根据 message_id 从数据库查询完整消息并发送
                            message = await self._get_message_by_id(message_id)
                            ws_message = ServerGeneralMessage(message=message)
                            await connection_manager.send_outbound_message(agent_id, ws_message)
                        else:
                            logger.warning(f"即时消息缺少 message_id: {message_data}")
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"无效的即时消息格式: {str(e)}")
                    except Exception as e:
                        logger.warning(f"处理即时消息失败 {agent_id}: {str(e)}")
                        # 处理失败可能是连接已断开，停止推送
                        break
                        
        except Exception as e:
            logger.error(f"即时消息订阅失败 {agent_id}: {str(e)}")
        finally:
            try:
                await redis_client.disconnect()
                logger.info(f"Agent {agent_id} 即时消息订阅已关闭")
            except:
                pass
    
    async def _handle_client_messages(self, websocket: WebSocket, agent_id: str):
        """
        处理客户端发送的消息循环
        
        这是主循环，负责接收和处理客户端发送的所有消息
        如发送消息、加入聊天、离开聊天、心跳等
        
        Args:
            websocket: WebSocket 连接对象
            agent_id: 智能体ID
        """
        try:
            while True:
                # 等待客户端消息
                data = await websocket.receive_text()
                
                try:
                    message_data = json.loads(data)
                    await self._handle_client_message(agent_id, message_data)
                    
                except json.JSONDecodeError:
                    logger.warning(f"收到无效的 JSON 消息: {data}")
                    await connection_manager.send_message(agent_id, {
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                    
        except WebSocketDisconnect:
            logger.info(f"Agent {agent_id} 主动断开连接")
            raise
        except Exception as e:
            logger.error(f"客户端消息处理出错 {agent_id}: {str(e)}")
            raise
    
    async def _handle_client_message(self, agent_id: str, message_data: Dict[str, Any]):
        """
        处理来自客户端的消息（DDD 设计，使用类型安全的模型）
        
        客户端通过 WebSocket 只能发送：
        1. 发送消息请求 (client_send_message)
        2. 心跳请求 (client_ping)
        
        注意：加入/离开聊天等操作应通过 HTTP API 完成，不应通过 WebSocket
        
        Args:
            agent_id: 发送者智能体ID
            message_data: 原始消息数据
        """
        try:
            # 使用工厂解析入站消息
            inbound_message: WSInboundMessage = WSMessageFactory.parse_inbound_message(message_data)
            logger.debug(f"收到来自 {agent_id} 的消息: {inbound_message.type}")
            
            # 根据消息类型分发处理
            if isinstance(inbound_message, ClientGeneralMessage):
                await self._process_client_message(agent_id, inbound_message)
            elif isinstance(inbound_message, ClientPingMessage):
                await self._process_client_ping(agent_id, inbound_message)
            else:
                logger.warning(f"无法处理的消息类型: {inbound_message.type}")
                error_msg = ServerErrorMessage(message=f"Unsupported message type: {inbound_message.type}")
                await connection_manager.send_outbound_message(agent_id, error_msg)
                
        except ValueError as e:
            logger.error(f"消息解析失败 {agent_id}: {str(e)}")
            error_msg = ServerErrorMessage(message=f"Invalid message format: {str(e)}")
            await connection_manager.send_outbound_message(agent_id, error_msg)
        except Exception as e:
            logger.error(f"处理客户端消息失败 {agent_id}: {str(e)}")
            error_msg = ServerErrorMessage(message=f"Failed to process message: {str(e)}")
            await connection_manager.send_outbound_message(agent_id, error_msg)
    
    async def _process_client_message(self, agent_id: str, message: ClientGeneralMessage):
        """
        处理客户端发送消息请求
        
        Args:
            agent_id: 发送者智能体ID
            message: 客户端消息请求
        """
        try:
            # 直接使用强类型模型的数据
            message_create = message.data
            
            # 仅存储消息到数据库，不进行分发
            db = Database()
            await db.connect()
            try:
                stored_message = await db.store_message(message_create, UUID(agent_id))
            finally:
                await db.disconnect()
            
            # 发送确认消息给发送者
            confirmation = ServerAckMessage(
                message_id=str(stored_message.id),
                timestamp=stored_message.timestamp.isoformat()
            )
            await connection_manager.send_outbound_message(agent_id, confirmation)
            
            # 异步分发消息给其他成员（使用位置参数）
            distribute_message(
                str(stored_message.id),
                str(stored_message.chat_id),
                str(stored_message.sender_id)
            )
            
            logger.info(f"消息已处理: {stored_message.id} from {agent_id}")
            
        except Exception as e:
            logger.error(f"处理发送消息失败: {str(e)}")
            error_msg = ServerErrorMessage(message=f"Failed to send message: {str(e)}")
            await connection_manager.send_outbound_message(agent_id, error_msg)
    
    async def _process_client_ping(self, agent_id: str, message: ClientPingMessage):
        """
        处理客户端心跳 ping 消息
        
        Args:
            agent_id: 智能体ID
            message: ping 消息模型
        """
        pong_response = ServerPongMessage(timestamp=asyncio.get_event_loop().time())
        await connection_manager.send_outbound_message(agent_id, pong_response)
    
    async def _get_message_by_id(self, message_id: str) -> Message:
        """
        根据 message_id 从数据库查询消息
        
        Args:
            message_id: 消息 ID
            
        Returns:
            Message: 消息对象
        """
        db = Database()
        await db.connect()
        try:
            return await db.get_message(UUID(message_id))
        finally:
            await db.disconnect()

    async def _cleanup_connection(self, agent_id: str):
        """
        清理连接相关资源
        
        Args:
            agent_id: 智能体ID
        """
        # 停止 Redis 订阅任务
        if agent_id in self.active_subscribers:
            subscriber_task = self.active_subscribers[agent_id]
            if not subscriber_task.done():
                subscriber_task.cancel()
                try:
                    await subscriber_task
                except asyncio.CancelledError:
                    pass
            del self.active_subscribers[agent_id]
        
        # 断开连接管理器中的连接
        await connection_manager.disconnect(agent_id)
        
        logger.info(f"Agent {agent_id} 连接清理完成")


# 全局 WebSocket 处理器实例
websocket_handler = WebSocketHandler()
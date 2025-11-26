"""
Huey 异步任务模块

负责处理消息分发、通知等异步任务
"""
import json
from uuid import UUID

from huey import RedisHuey, crontab

from .redis_client import RedisClient
from .redis_channels import RedisChannels
from .db import Database
from .logger import get_logger

# 使用统一的日志系统
logger = get_logger("TaskWorker")

# Huey 实例（未初始化，由 init_huey() 设置）
huey = None

# 全局 Redis 客户端（由 init_huey 设置）
_redis_client = None

# 任务函数引用（初始化后设置）
distribute_message = None
cleanup_offline_messages = None


def init_huey(redis_url: str):
    """
    初始化 Huey 实例和 Redis 客户端
    
    Args:
        redis_url: Redis 连接地址
    """
    global huey, _redis_client, distribute_message, cleanup_offline_messages
    huey = RedisHuey("chalk_server", url=redis_url)
    _redis_client = RedisClient(redis_url)
    
    # 注册任务
    distribute_message = huey.task()(_distribute_message_impl)
    cleanup_offline_messages = huey.periodic_task(crontab(minute="*/30"))(_cleanup_offline_messages_impl)


def _distribute_message_impl(message_id: str, chat_id: str, sender_id: str):
    """
    分发消息到聊天成员
    
    根据用户在线状态采用不同策略：
    - 在线用户：实时推送到 WebSocket
    - 离线用户：存储为离线消息，等待上线时推送
    
    Args:
        message_id: 消息ID
        chat_id: 聊天ID  
        sender_id: 发送者ID
    """
    logger.info(f"开始分发消息 {message_id} 到聊天 {chat_id}")
    
    try:
        # 初始化数据库连接
        db = Database()
        
        # 连接数据库和Redis（同步方式，因为Huey任务是同步的）
        import asyncio
        
        async def _distribute():
            await db.connect()
            await _redis_client.connect()
            
            try:
                # 获取聊天成员列表
                member_ids = await db.get_chat_member_ids(UUID(chat_id))
                logger.info(f"聊天 {chat_id} 共有 {len(member_ids)} 个成员")
                
                # 获取完整的消息对象
                message = await db.get_message(UUID(message_id))
                
                # 使用正确的出站消息模型
                from .models import ServerGeneralMessage
                ws_message = ServerGeneralMessage(message=message)
                message_data_json = ws_message.model_dump_json()
                
                # 统计在线/离线用户数
                online_count = 0
                offline_count = 0
                
                # 分发消息到每个成员（排除发送者）
                for member_id in member_ids:
                    if str(member_id) != sender_id:
                        # 检查用户是否在线
                        is_online = await _redis_client.is_user_online(str(member_id))
                        
                        if is_online:
                            # 在线用户：发布 message_id 到即时频道
                            instant_message_data = {
                                "message_id": message_id,
                                "chat_id": chat_id,
                                "timestamp": message.timestamp.isoformat()
                            }
                            channel = RedisChannels.user_inbox_instant(str(member_id))
                            await _redis_client.publish_to_channel(channel, json.dumps(instant_message_data))
                            logger.debug(f"即时消息 ID 已发布到频道: {channel}")
                            online_count += 1
                        else:
                            # 离线用户：使用 Redis 客户端封装的方法存储 message_id
                            success = await _redis_client.store_offline_message_id(
                                user_id=str(member_id),
                                message_id=message_id,
                                chat_id=chat_id,
                                timestamp=message.timestamp.isoformat()
                            )
                            
                            if success:
                                logger.debug(f"离线消息 ID 已存储给: {member_id}")
                            else:
                                logger.warning(f"存储离线消息 ID 失败: {member_id}")
                            
                            offline_count += 1
                
                logger.info(f"消息 {message_id} 分发完成: 在线 {online_count} 人，离线 {offline_count} 人")
                
            finally:
                await db.disconnect()
                await _redis_client.disconnect()
        
        # 运行异步任务
        asyncio.run(_distribute())
        
    except Exception as e:
        logger.error(f"分发消息 {message_id} 失败: {str(e)}", exc_info=True)
        # 重新抛出异常让Huey进行重试
        raise


def _cleanup_offline_messages_impl():
    """
    定期清理Redis中的离线消息，防止内存无限增长
    
    清理策略：
    1. 清理超过1000条的离线消息，只保留最新的1000条
    2. 删除超过30天的离线消息Key（通过Redis TTL自动过期）
    """
    logger.info("开始清理Redis中的离线消息...")
    
    try:
        async def _cleanup():
            await _redis_client.connect()
            
            try:
                if not _redis_client.redis:
                    logger.warning("Redis未连接，跳过清理任务")
                    return
                
                # 扫描所有离线消息 Key
                pattern = "user:inbox:offline:*"
                cleaned_count = 0
                
                # 使用scan_iter遍历所有匹配的key
                async for key in _redis_client.redis.scan_iter(match=pattern):
                    try:
                        # 获取当前列表长度
                        list_length = await _redis_client.redis.llen(key)
                        
                        if list_length > 1000:
                            # 保留最新的1000条消息
                            await _redis_client.redis.ltrim(key, 0, 999)
                            logger.debug(f"清理离线消息Key: {key} (原长度: {list_length})")
                            cleaned_count += 1
                            
                    except Exception as e:
                        logger.warning(f"清理Key {key} 时出错: {str(e)}")
                        continue
                
                if cleaned_count > 0:
                    logger.info(f"离线消息清理完成，共清理了 {cleaned_count} 个Key")
                else:
                    logger.info("没有需要清理的离线消息")
                
            finally:
                await _redis_client.disconnect()
        
        # 运行异步清理任务
        import asyncio
        asyncio.run(_cleanup())
        
    except Exception as e:
        logger.error(f"清理离线消息失败: {str(e)}", exc_info=True)
"""
服务器初始化模块
职责：数据库初始化、迁移、重置、环境检查等启动相关操作
"""
import sys
import redis
from pathlib import Path

from .logger import get_logger
from .config import get_settings
from .tables import (
    get_database, 
    get_all_tables,
    AgentTable,
    ChatTable,
    ChatMemberTable,
    MessageTable
)

logger = get_logger("ServerInit")


def init_database():
    """初始化数据库表 - 安全的重建方式"""
    db = get_database()
    db.connect()
    
    try:
        # 获取所有表模型
        tables = get_all_tables()
        
        # 先删除所有表（按依赖关系逆序）
        # MessageTable依赖ChatTable和AgentTable
        # ChatMemberTable依赖ChatTable和AgentTable  
        # ChatTable和AgentTable相互独立
        drop_order = [MessageTable, ChatMemberTable, ChatTable, AgentTable]
        
        for table in drop_order:
            if table.table_exists():
                logger.info(f"删除表: {table._meta.table_name}")
                table.drop_table()
        
        # 重新创建所有表（按依赖关系正序）
        create_order = [AgentTable, ChatTable, ChatMemberTable, MessageTable]
        
        for table in create_order:
            logger.info(f"创建表: {table._meta.table_name}")
            table.create_table()
            
        logger.info("✅ 数据库初始化完成")
        
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


def migrate_database():
    """数据库迁移 - 保留数据的升级方式"""
    db = get_database()
    db.connect()
    
    try:
        # 检查表是否存在，不存在则创建
        tables = get_all_tables()
        
        for table in tables:
            if not table.table_exists():
                logger.info(f"创建新表: {table._meta.table_name}")
                table.create_table()
            else:
                # TODO: 这里可以添加字段级别的迁移逻辑
                # 比如检查字段是否存在，添加新字段等
                logger.debug(f"表已存在: {table._meta.table_name}")
        
        logger.info("✅ 数据库迁移完成")
        
    except Exception as e:
        logger.error(f"❌ 数据库迁移失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


def reset_database():
    """重置数据库 - 完全清空重建（仅开发环境使用）"""
    logger.warning("⚠️ 即将完全重置数据库，所有数据将丢失！")
    init_database()


def check_database():
    """检查数据库连接和表状态"""
    db = get_database()
    try:
        db.connect()
        tables = get_all_tables()
        
        logger.info("🔍 检查数据库状态...")
        for table in tables:
            exists = "✅" if table.table_exists() else "❌"
            logger.info(f"{exists} {table._meta.table_name}")
        
        db.close()
        return True
    except Exception as e:
        logger.error(f"❌ 数据库检查失败: {e}", exc_info=True)
        return False


def check_redis() -> bool:
    """
    检查 Redis 连接是否可用
    
    Returns:
        bool: Redis 是否可用
    """
    settings = get_settings()
    
    try:
        # 创建 Redis 客户端并测试连接
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        client.close()
        return True
        
    except redis.ConnectionError as e:
        logger.error(f"❌ Redis 连接失败: 无法连接到 {settings.redis_url}")
        logger.error(f"   错误信息: {e}")
        return False
    except redis.TimeoutError as e:
        logger.error(f"❌ Redis 连接超时: {settings.redis_url}")
        logger.error(f"   错误信息: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Redis 检查失败: {e}", exc_info=True)
        return False


def check_sqlite() -> bool:
    """
    检查 SQLite 数据库文件和连接
    
    Returns:
        bool: SQLite 是否可用
    """
    settings = get_settings()
    db_path = Path(settings.sqlite_path)
    
    try:
        # 检查目录是否可写
        db_dir = db_path.parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
        
        # 测试数据库连接
        db = get_database()
        db.connect()
        db.close()
        
        return True
        
    except PermissionError as e:
        logger.error(f"❌ SQLite 权限错误: 无法访问 {settings.sqlite_path}")
        logger.error(f"   错误信息: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ SQLite 检查失败: {e}", exc_info=True)
        return False


def check_environment() -> bool:
    """
    检查所有环境依赖
    
    Returns:
        bool: 所有检查是否通过
    """
    checks = [
        ("SQLite", check_sqlite),
        ("Redis", check_redis),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            logger.error(f"❌ {name} 检查出错: {e}", exc_info=True)
            results.append(False)
    
    if all(results):
        return True
    else:
        logger.error("="*60)
        logger.error("❌ 环境检查失败，部分依赖不可用")
        logger.error("="*60)
        logger.error("💡 请检查：")
        logger.error("   1. Redis 服务器是否启动")
        logger.error("   2. Redis 连接配置是否正确 (.env 文件中的 REDIS_URL)")
        logger.error("   3. SQLite 数据库文件路径是否可写")
        logger.error("="*60)
        return False

from uuid import UUID
from peewee import IntegrityError

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket
from fastapi.responses import HTMLResponse

from .config import get_settings
from .db import Database
from .models import UserRegister, UserAuth, ChatCreate, MessageCreate, User, Chat, Message
from .services import MessageService, ChatService, UserService
from .websocket_handler import websocket_handler

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root():
    """
    根路径 - 服务状态检查
    
    返回:
    - 200: 服务运行状态和项目链接（HTML）
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chalk Server</title>
    </head>
    <body>
        <p>Chalk is Running, <a href="https://github.com/zhixiangxue/chalk-ai" target="_blank">View on GitHub →</a></p>
    </body>
    </html>
    """


# 明确的依赖注入函数
async def get_db():
    """获取数据库连接"""
    settings = get_settings()
    db = Database(settings.sqlite_path)
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


def get_user_service(
        db: Database = Depends(get_db)
) -> UserService:
    return UserService(db)


def get_message_service(
        db: Database = Depends(get_db)
) -> MessageService:
    """
    获取消息服务（重构后简化版本）
    
    移除了 Redis 依赖，消息分发通过 Huey 任务处理
    """
    return MessageService(db)


def get_chat_service(
        db: Database = Depends(get_db)
) -> ChatService:
    return ChatService(db)


@router.post("/auth/register", response_model=User)
async def register(user_data: UserRegister, service: UserService = Depends(get_user_service)):
    """
    用户注册
    
    HTTP调用方式:
    POST /auth/register
    Content-Type: application/json
    Body: {
        "name": "用户名",
        "password": "密码",
        "bio": "个人简介"
    }
    
    功能:
    - 注册新用户账号
    - 用户名必须唯一
    - 密码会被加密存储
    
    返回:
    - 200: 成功创建的User对象
    - 409: 用户名已存在
    - 422: 请求参数验证失败
    """
    try:
        return await service.register_user(user_data)
    except IntegrityError as e:
        if "UNIQUE constraint failed" in str(e) or "name" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"用户名 '{user_data.name}' 已存在，请选择其他用户名"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"数据库错误: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"注册失败: {str(e)}"
        )


@router.post("/auth/login", response_model=User)
async def login(auth_data: UserAuth, service: UserService = Depends(get_user_service)):
    """
    用户登录
    
    HTTP调用方式:
    POST /auth/login
    Content-Type: application/json
    Body: {
        "name": "用户名",
        "password": "密码"
    }
    
    功能:
    - 验证用户名和密码
    - 返回用户信息
    
    返回:
    - 200: User对象
    - 404: 用户不存在
    - 401: 密码错误
    - 422: 请求参数验证失败
    """
    try:
        return await service.login_user(auth_data)
    except ValueError as e:
        error_msg = str(e)
        if "密码错误" in error_msg:
            raise HTTPException(status_code=401, detail=error_msg)
        elif "不存在" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)


@router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: UUID, service: UserService = Depends(get_user_service)):
    """
    根据ID获取用户信息
    
    HTTP调用方式:
    GET /users/{user_id}
    
    功能:
    - 根据UUID获取用户的详细信息
    - 用于客户端从 ID 恢复用户对象
    
    路径参数:
    - user_id: 用户的UUID
    
    返回:
    - 200: User对象，包含用户信息
    - 404: 用户不存在
    - 422: UUID格式错误
    """
    try:
        return await service.get_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/users/by-name/{name}", response_model=list[User])
async def get_users_by_name(name: str, service: UserService = Depends(get_user_service)):
    """
    根据用户名获取用户信息（可能返回多个同名用户）
    
    HTTP调用方式:
    GET /users/by-name/{name}
    
    功能:
    - 根据用户名查询所有同名用户
    - 用于客户端查找用户
    
    路径参数:
    - name: 用户名
    
    返回:
    - 200: User对象列表（可能为空）
    """
    return await service.get_users_by_name(name)


@router.post("/chats", response_model=Chat)
async def create_chat(chat: ChatCreate, user_id: UUID = Header(..., alias="X-User-ID"),
                      service: ChatService = Depends(get_chat_service)):
    """
    创建新的聊天房间
    
    HTTP调用方式:
    POST /chats
    Headers: {
        "X-User-ID": "创建者用户的UUID"
    }
    Content-Type: application/json
    Body: {
        "type": "group", // 或 "direct"
        "name": "聊天房间名称",
        "members": ["成员UUID列表"]
    }
    
    功能:
    - 创建一个新的聊天房间，指定创建者
    - 创建者自动成为房间成员和管理员
    - 只有创建者才能删除房间
    
    请求头:
    - X-User-ID: 创建者的用户ID
    
    返回:
    - 200: 成功创建的Chat对象
    - 400: 私聊规则验证失败
    - 422: 请求参数验证失败
    """
    try:
        return await service.create_chat(chat, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: UUID, user_id: UUID = Header(..., alias="X-User-ID"),
                      service: ChatService = Depends(get_chat_service)):
    """
    删除指定的聊天房间（仅创建者可用）
    
    HTTP调用方式:
    DELETE /chats/{chat_id}
    Headers: {
        "X-Agent-ID": "创建者的UUID"
    }
    
    功能:
    - 仅创建者可以删除聊天房间
    - 删除后所有相关数据（消息、成员关系）都会被清理
    
    路径参数:
    - chat_id: 要删除的聊天房间ID
    
    请求头:
    - X-Agent-ID: 创建者的智能体ID
    
    返回:
    - 200: {"status": "deleted"} 删除成功
    - 403: {"error": "没有权限"} 非创建者试图删除
    - 404: 聊天房间不存在
    - 422: UUID格式错误
    """
    try:
        success = await service.delete_chat(chat_id, user_id)
        if success:
            return {"status": "deleted"}
        else:
            return {"status": "failed", "error": "Chat not found"}
    except PermissionError as e:
        return {"error": str(e)}


@router.get("/chats", response_model=list[Chat])
async def list_chats(user_id: UUID = Header(..., alias="X-User-ID"),
                     service: ChatService = Depends(get_chat_service)):
    """
    获取智能体参与的所有聊天房间列表
    
    HTTP调用方式:
    GET /chats
    Headers: {
        "X-Agent-ID": "智能体的UUID"
    }
    
    功能:
    - 返回指定智能体已加入的所有聊天房间
    - 可用于显示智能体的聊天房间列表
    
    请求头:
    - X-Agent-ID: 要查询的智能体ID
    
    返回:
    - 200: Chat对象数组，包含房间信息
    - 404: 智能体不存在
    - 422: UUID格式错误
    """
    return await service.list_chats(user_id)


@router.get("/chats/{chat_id}", response_model=Chat)
async def get_chat(chat_id: UUID, user_id: UUID = Header(..., alias="X-User-ID"),
                   service: ChatService = Depends(get_chat_service)):
    """
    获取指定聊天房间的详细信息
    
    HTTP调用方式:
    GET /chats/{chat_id}
    Headers: {
        "X-Agent-ID": "请求者的UUID"
    }
    
    功能:
    - 获取指定聊天的详细信息
    - 需要是聊天成员才能访问
    
    路径参数:
    - chat_id: 聊天房间ID
    
    请求头:
    - X-Agent-ID: 请求者的智能体ID
    
    返回:
    - 200: Chat对象，包含房间信息
    - 403: 没有权限访问（不是成员）
    - 404: 聊天房间不存在
    - 422: UUID格式错误
    """
    try:
        return await service.get_chat(chat_id, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/chats/{chat_id}/members", response_model=list[User])
async def list_members(chat_id: UUID, service: ChatService = Depends(get_chat_service)):
    """
    获取指定聊天房间的所有成员列表
    
    HTTP调用方式:
    GET /chats/{chat_id}/members
    
    功能:
    - 返回指定聊天房间中的所有智能体成员
    - 可用于显示房间成员列表
    
    路径参数:
    - chat_id: 要查询的聊天房间ID
    
    返回:
    - 200: Agent对象数组，包含所有成员信息
    - 404: 聊天房间不存在
    - 422: UUID格式错误
    """
    return await service.list_members(chat_id)


@router.get("/chats/{chat_id}/messages", response_model=list[Message])
async def list_messages(
        chat_id: UUID,
        page: int = 1,
        page_size: int = 50,
        service: ChatService = Depends(get_chat_service)
):
    """
    获取指定聊天房间的消息列表
    
    HTTP调用方式:
    GET /chats/{chat_id}/messages?page=1&page_size=50
    
    功能:
    - 获取指定聊天房间的消息列表
    - 消息按时间倒序排列（最新的在前）
    - 支持分页加载，默认每页 50 条
    
    路径参数:
    - chat_id: 要查询的聊天房间ID
    
    查询参数:
    - page: 页码，从 1 开始（可选，默认为 1）
    - page_size: 每页消息数量（可选，默认为 50，最大 100）
    
    返回:
    - 200: Message对象数组，包含消息列表
    - 404: 聊天房间不存在
    - 422: UUID格式错误或参数错误
    
    注意:
    - 消息按时间倒序排列，第 1 页是最新的消息
    - page_size 最大值为 100，超过将被限制
    """
    # 限制每页最大数量防止滥用
    if page_size > 100:
        page_size = 100
    if page < 1:
        page = 1

    return await service.list_messages(chat_id, page, page_size)


@router.post("/chats/{chat_id}/join")
async def join_chat(chat_id: UUID, user_id: UUID = Header(..., alias="X-User-ID"),
                    service: ChatService = Depends(get_chat_service)):
    """
    智能体加入指定的聊天房间
    
    HTTP调用方式:
    POST /chats/{chat_id}/join
    Headers: {
        "X-Agent-ID": "智能体的UUID"
    }
    
    功能:
    - 将指定的智能体加入到聊天房间中
    - 加入后该智能体可以在此房间中发送和接收消息
    
    路径参数:
    - chat_id: 要加入的聊天房间ID
    
    请求头:
    - X-Agent-ID: 要加入的智能体ID
    
    返回:
    - 200: {"status": "joined"} 加入成功
    - 404: 聊天房间或智能体不存在
    - 422: UUID格式错误
    """
    await service.join_chat(chat_id, user_id)
    return {"status": "joined"}


@router.post("/chats/{chat_id}/leave")
async def leave_chat(chat_id: UUID, user_id: UUID = Header(..., alias="X-User-ID"),
                     service: ChatService = Depends(get_chat_service)):
    """
    退出指定的聊天房间
    
    HTTP调用方式:
    POST /chats/{chat_id}/leave
    Headers: {
        "X-Agent-ID": "智能体的UUID"
    }
    
    功能:
    - 普通成员退出：移除成员关系
    - 创建者退出：自动删除整个聊天房间
    
    路径参数:
    - chat_id: 要退出的聊天房间ID
    
    请求头:
    - X-Agent-ID: 要退出的智能体ID
    
    返回:
    - 200: {"status": "left"} 退出成功
    - 200: {"status": "deleted"} 创建者退出，房间已删除
    - 404: 聊天房间或智能体不存在
    - 422: UUID格式错误
    """
    success = await service.leave_chat(chat_id, user_id)
    if success:
        # 检查房间是否还存在（判断是普通退出还是删除）
        members = await service.list_members(chat_id)
        if not members:  # 房间已被删除
            return {"status": "deleted"}
        else:
            return {"status": "left"}
    else:
        return {"status": "failed", "error": "Chat or agent not found"}


@router.delete("/chats/{chat_id}/members/{user_id}")
async def remove_member(
        chat_id: UUID,
        user_id: UUID,
        requester_id: UUID = Header(..., alias="X-User-ID"),
        service: ChatService = Depends(get_chat_service)
):
    """
    移除聊天房间成员（仅创建者可用）
    
    HTTP调用方式:
    DELETE /chats/{chat_id}/members/{agent_id}
    Headers: {
        "X-Agent-ID": "创建者的UUID"
    }
    
    功能:
    - 仅创建者可以移除其他成员
    - 不能移除自己（应使用退出功能）
    - 被移除的成员将无法再看到聊天内容
    
    路径参数:
    - chat_id: 聊天房间ID
    - agent_id: 要移除的智能体ID
    
    请求头:
    - X-Agent-ID: 创建者的智能体ID
    
    返回:
    - 200: {"status": "removed"} 移除成功
    - 403: {"error": "没有权限"} 非创建者试图移除成员
    - 400: {"error": "不能移除自己"} 试图移除自己
    - 404: 聊天房间或智能体不存在
    - 422: UUID格式错误
    """
    try:
        success = await service.remove_member(chat_id, user_id, requester_id)
        if success:
            return {"status": "removed"}
        else:
            return {"status": "failed", "error": "Chat or agent not found, or agent not in chat"}
    except PermissionError as e:
        return {"error": str(e)}
    except ValueError as e:
        return {"error": str(e)}


@router.post("/chats/{chat_id}/members/{user_id}")
async def add_member(
        chat_id: UUID,
        user_id: UUID,
        requester_id: UUID = Header(..., alias="X-User-ID"),
        service: ChatService = Depends(get_chat_service)
):
    """
    添加新成员到聊天房间（仅创建者可用）
    
    HTTP调用方式:
    POST /chats/{chat_id}/members/{agent_id}
    Headers: {
        "X-Agent-ID": "创建者的UUID"
    }
    
    功能:
    - 仅创建者可以添加新成员
    - 被添加的成员将能够看到聊天内容并参与对话
    - 如果成员已经在聊天中，操作将失败
    - 私聊不能添加成员
    
    路径参数:
    - chat_id: 聊天房间ID
    - agent_id: 要添加的智能体ID
    
    请求头:
    - X-Agent-ID: 创建者的智能体ID
    
    返回:
    - 200: {"status": "added"} 添加成功
    - 400: {"error": "私聊不能添加成员"}
    - 403: {"error": "没有权限"} 非创建者试图添加成员
    - 409: {"status": "already_member"} 成员已经在聊天中
    - 404: 聊天房间或智能体不存在
    - 422: UUID格式错误
    """
    try:
        success = await service.add_member(chat_id, user_id, requester_id)
        if success:
            return {"status": "added"}
        else:
            return {"status": "already_member", "error": "Agent already in chat or not found"}
    except PermissionError as e:
        return {"error": str(e)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket 端点 - 实时通信
    
    WebSocket 连接方式:
    ws://localhost:8000/ws/{user_id}
    
    功能:
    - 建立 User 的 WebSocket 连接
    - 处理实时消息收发
    - 管理在线状态
    - 处理离线消息
    
    路径参数:
    - user_id: 用户的UUID
    
    消息格式:
    客户端发送消息格式:
    {
        "type": "send_message",
        "data": {
            "chat_id": "uuid",
            "content": "消息内容",
            "type": "text",
            "parent_id": "uuid", // 可选
            "mentions": ["uuid1", "uuid2"] // 可选
        }
    }
    
    服务端返回消息格式:
    {
        "type": "message_sent",
        "message_id": "uuid",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    注意:
    - 这个 WebSocket 端点取代了原有的 HTTP POST /messages 端点
    - 客户端现在通过 WebSocket 发送消息，而不是 HTTP 请求
    - 支持实时消息推送和离线消息处理
    """
    await websocket_handler.handle_connection(websocket, user_id)

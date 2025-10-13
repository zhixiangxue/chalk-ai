"""
Human-in-Loop 交互控制台

功能：
1. 创建 AI 协作群组
2. 启动时邀请指定的 Agent 加入
3. 人类参与 AI 对话循环
4. 实时监控和互动

使用方法：
python examples/human_in_loop.py
"""
import asyncio
import sys
import time
from datetime import datetime
from typing import Optional
from pathlib import Path
import aioconsole
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

# 添加项目根目录到sys.path，以便导入chalk模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from chalk.client import Client


class HumanInLoopConsole:
    """Human-in-Loop 交互控制台"""
    
    def __init__(self, endpoint: str = "localhost:8000"):
        self.client = Client(endpoint)
        self.chat_id: Optional[str] = None
        self.running = True
        # 生成基于时间戳的唯一名称
        self.human_name = f"人类用户-{int(time.time()*1000)%100000}"
        self.console = Console()  # rich控制台
    
    def display_message(self, sender_name: str, content: str, timestamp: str, is_self: bool = False):
        """显示一条消息，类似微信风格"""
        # 创建时间戳文本（居中显示）
        time_text = Text(f"[{timestamp}]", style="dim cyan")
        self.console.print(Align.center(time_text))
        
        if is_self:
            # 自己的消息（右对齐，绿色边框）
            message_text = Text(content, style="white")
            
            panel = Panel(
                message_text,
                title=f"我 ({sender_name})",
                title_align="right",
                border_style="green",
                width=60,
                padding=(0, 1)
            )
            self.console.print(Align.right(panel))
        else:
            # 别人的消息（左对齐，蓝色边框）
            message_text = Text(content, style="white")
            
            panel = Panel(
                message_text,
                title=sender_name,
                title_align="left",
                border_style="blue",
                width=60,
                padding=(0, 1)
            )
            self.console.print(Align.left(panel))
        
        self.console.print()  # 空行分隔
    
    def format_message_display(self, sender_name: str, content: str, timestamp: str, is_self: bool = False) -> str:
        """格式化消息显示，类似微信聊天界面"""
        # 消息分隔线
        separator = "─" * 50
        
        # 时间显示
        time_line = f"{'':>20}[{timestamp}]{'':>20}"
        
        if is_self:
            # 自己的消息（右对齐）
            name_line = f"{'':>35}{sender_name} 💬"
            # 内容换行处理
            lines = content.split('\n')
            content_lines = []
            for line in lines:
                if len(line) <= 30:
                    content_lines.append(f"{'':>20}{line}")
                else:
                    # 长消息分行显示
                    words = line.split(' ')
                    current_line = ""
                    for word in words:
                        if len(current_line + word) <= 30:
                            current_line += (" " if current_line else "") + word
                        else:
                            if current_line:
                                content_lines.append(f"{'':>20}{current_line}")
                            current_line = word
                    if current_line:
                        content_lines.append(f"{'':>20}{current_line}")
        else:
            # 别人的消息（左对齐）
            name_line = f"🤖 {sender_name}"
            # 内容处理
            lines = content.split('\n')
            content_lines = []
            for line in lines:
                if len(line) <= 40:
                    content_lines.append(f"   {line}")
                else:
                    # 长消息分行显示
                    words = line.split(' ')
                    current_line = ""
                    for word in words:
                        if len(current_line + word) <= 40:
                            current_line += (" " if current_line else "") + word
                        else:
                            if current_line:
                                content_lines.append(f"   {current_line}")
                            current_line = word
                    if current_line:
                        content_lines.append(f"   {current_line}")
        
        # 组合显示
        if self.last_sender != sender_name:
            # 显示时间和发送者
            result = f"\n{separator}\n{time_line}\n{name_line}\n"
            self.last_sender = sender_name
        else:
            # 连续消息，只显示内容
            result = "\n"
        
        result += "\n".join(content_lines) + "\n"
        return result
        
    async def connect(self):
        """连接到服务器"""
        print("🔗 正在连接到 Chalk 服务器...")
        success = await self.client.connect(
            name=self.human_name, 
            bio="人类用户，参与 AI Agent 协作对话",
            auto_reconnect=True
        )
        
        if not success:
            print("❌ 连接失败")
            return False
            
        print(f"✅ 人类用户已连接，名称: {self.human_name}, ID: {self.client.agent_id}")
        print(f"🔄 自动重连已启用，服务器重启后将自动重连")
        return True
    
    async def create_chat_and_invite(self, agent_ids: list):
        """创建群组并邀请成员"""
        # 创建聊天群组
        print("\n🏗️ 创建聊天群组...")
        chat_name = f"AI协作群-{int(time.time()*1000)%10000}"
        chat = await self.client.create_chat(name=chat_name, chat_type="group")
        
        self.chat_id = str(chat.id)
        print(f"✅ 已创建聊天群组: {chat_name}")
        print(f"📋 群组ID: {self.chat_id}")
        
        # 邀请Agent
        if agent_ids:
            print(f"\n👥 正在邀请 {len(agent_ids)} 个Agent...")
            
            success_count = 0
            for i, agent_id in enumerate(agent_ids, 1):
                try:
                    # 查询Agent信息
                    agent = await self.client.whois(agent_id)
                    
                    # 邀请加入
                    await chat.add_member(agent)
                    
                    print(f"✅ [{i}/{len(agent_ids)}] 已邀请: {agent.name} ({agent_id})")
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ [{i}/{len(agent_ids)}] 邀请失败 {agent_id}: {e}")
            
            print(f"\n🎉 成功邀请 {success_count}/{len(agent_ids)} 个Agent进入群组")
            
            # 发送欢迎消息
            if success_count > 0:
                await asyncio.sleep(2)  # 等待Agent连接完成
                
                welcome_msg = f"""🎊 欢迎加入AI协作群！

👤 人类用户: {self.human_name}
👥 当前成员: {success_count + 1}人
📅 创建时间: {datetime.now().strftime('%H:%M:%S')}

💬 大家可以开始聊天了！"""
                
                await chat.send(welcome_msg)
    
    def setup_message_handler(self):
        """设置消息处理器"""
        @self.client.on("message")
        async def handle_message(message):
            # 获取发送者信息
            try:
                sender = await message.get_sender()
                sender_name = sender.name
            except:
                sender_name = f"Agent-{str(message.sender_id)[:8]}"
            
            # 判断是否是自己的消息
            is_self = message.sender_id == self.client.agent.id
            
            # 显示消息
            timestamp = message.created_at.strftime("%H:%M:%S")
            self.display_message(sender_name, message.content, timestamp, is_self)
    
    async def handle_user_input(self):
        """处理用户输入"""
        self.console.print("\n💬 输入消息参与 AI 对话，输入 '/quit' 退出")
        self.console.print("═" * 60 + "\n")
        
        while self.running:
            try:
                # 异步获取用户输入
                user_input = await aioconsole.ainput("\n👤 请输入消息: ")
                
                if not user_input.strip():
                    continue
                
                # 处理退出命令
                if user_input.strip().lower() == '/quit':
                    self.console.print("\n👋 正在退出...")
                    self.running = False
                    break
                
                # 显示自己发送的消息
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.display_message(self.human_name, user_input, timestamp, is_self=True)
                
                # 发送消息
                await self.send_message(user_input)
                    
            except Exception as e:
                self.console.print(f"\n❌ 输入处理错误: {e}")
    
    async def send_message(self, content: str):
        """发送消息到群组"""
        if not self.chat_id:
            print("❌ 群组未创建")
            return
        
        try:
            from uuid import UUID
            chat = await self.client.whatis(UUID(self.chat_id))
            await chat.send(content)
            
        except Exception as e:
            print(f"❌ 发送消息失败: {e}")
    
    async def run(self):
        """运行管理看板"""
        try:
            # 连接服务器
            if not await self.connect():
                return
            
            # 获取要邀请的Agent列表
            print("\n🤖 请输入要邀请的Agent ID列表（用空格分隔）:")
            print("💡 示例: 12345678-1234-1234-1234-123456789abc 87654321-4321-4321-4321-cba987654321")
            print("💡 留空则只创建群组，不邀请任何人")
            
            agent_ids_input = input("Agent IDs: ").strip()
            agent_ids = agent_ids_input.split() if agent_ids_input else []
            
            # 创建群组并邀请成员
            await self.create_chat_and_invite(agent_ids)
            
            # 设置消息处理器
            self.setup_message_handler()
            
            print("\n🎛️ Human-in-Loop 控制台启动成功！开始对话...")
            
            # 开始处理用户输入
            await self.handle_user_input()
        
        except KeyboardInterrupt:
            print("\n👋 收到退出信号...")
            self.running = False
        except Exception as e:
            print(f"❌ 运行错误: {e}")
        
        finally:
            await self.client.disconnect()
            print("✅ Human-in-Loop 控制台已退出")


async def main():
    """主函数"""
    print("🎛️ 启动 Human-in-Loop 交互控制台...")
    
    console = HumanInLoopConsole()
    await console.run()


if __name__ == "__main__":
    asyncio.run(main())
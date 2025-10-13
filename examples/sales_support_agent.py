"""
售前支持 Agent 示例

功能：
1. 接入 chalk，打印 Agent ID
2. 简单的对话 + 上下文记忆

使用方法：
python examples/sales_support_agent.py
"""
import asyncio
import os
import sys
import time
from typing import Optional, List
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

# 添加项目根目录到sys.path，以便导入chalk模块
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"⚙️ 已加载配置文件: {env_path}")
except ImportError:
    print("⚠️ 未安装 python-dotenv，跳过 .env 文件加载")

from chalk.client import Client


class SalesSupportAgent:
    """售前支持智能代理 - 演示版"""
    
    def __init__(self, endpoint: str = "localhost:8000"):
        self.client = Client(endpoint)
        self.llm: Optional[ChatOpenAI] = None
        self.messages: List = []  # 简单的消息历史
        # 生成基于时间戳的唯一名称
        self.agent_name = f"售前专员-{int(time.time()*1000)%100000}"
        self.console = Console()  # rich控制台
        self.setup_llm()
    
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
                title=f"售前专员 ({sender_name})",
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
    
    def setup_llm(self):
        """设置大语言模型"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ 未设置 OPENAI_API_KEY，将使用模拟回复")
            return
        
        try:
            base_url = os.getenv("OPENAI_BASE_URL")
            model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            
            config = {"model": model_name, "temperature": 0.8, "api_key": api_key}
            if base_url:
                config["base_url"] = base_url
                print(f"🔗 使用 API: {base_url}")
            
            self.llm = ChatOpenAI(**config)
            
            # 添加系统消息
            self.messages.append(SystemMessage(content="""你是一个专业的售前支持专员，负责产品销售、商务咨询和售前服务。

【专业职责范围】
你只处理以下类型的问题：
1. 产品价格和套餐咨询（价格、优惠、折扣、费用等）
2. 购买流程和付费方式（如何购买、支付方式、续费等）
3. 产品功能介绍和对比（版本区别、功能特点、竞品对比等）
4. 商务合作和定制方案（企业合作、大客户服务、定制开发等）
5. 试用和演示申请

【非职责范围】
以下问题不属于你的职责，必须回复"SKIP"：
- 技术故障和问题排查（属于客服专员）
- 账户问题和权限管理（属于客服专员）
- 产品使用教学和指导（属于客服专员）
- 用户投诉和售后服务（属于客服专员）
- 闲聊、天气、新闻等与产品无关的话题
- 其他与销售无关的问题

【回复规则】
1. 严格判断：仔细分析用户问题，只有明确属于你的专业范围才回复
2. SKIP机制：如果问题不在上述"专业职责范围"内，直接回复"SKIP"，不要尝试回答或转移话题
3. @提及例外：当被@提及时，即使不在专业范围也要礼貌回应，说明你的职责范围并引导用户找正确的人
4. 专业聚焦：只提供销售和商务咨询服务，不要涉及技术支持话题

【示例】
✅ 应该回复的问题：
- "这个产品多少钱？"
- "企业版和个人版有什么区别？"
- "我想购买100个账号，有优惠吗？"
- "@售前专员 在吗？"（被@提及）

❌ 应该回复SKIP的问题：
- "我无法登录系统" → SKIP
- "如何创建群组？" → SKIP
- "今天天气真好" → SKIP
- "我需要反馈一个Bug" → SKIP

请严格遵守以上规则，保持专业边界。"""))
            print("✅ LangChain 初始化成功")
            
        except Exception as e:
            print(f"❌ LangChain 初始化失败: {e}")
    
    async def process_message(self, message) -> str:
        """处理用户消息"""
        user_content = message.content
        
        if not self.llm:
            return "抱歉，我需要设置 API 才能回复。请配置 OPENAI_API_KEY 环境变量。"
        
        try:
            # 添加用户消息到历史
            self.messages.append(HumanMessage(content=user_content))
            
            # 保持消息历史在合理长度内（最多10轮对话）
            if len(self.messages) > 21:  # 1系统 + 20消息
                self.messages = [self.messages[0]] + self.messages[-20:]
            
            # 调用LLM
            response = await self.llm.ainvoke(self.messages)
            
            # 如果LLM回复SKIP，表示不在专业范围内
            if response.content.strip().upper() == "SKIP":
                return "SKIP"
            
            # 添加AI回复到历史
            self.messages.append(AIMessage(content=response.content))
            
            return response.content
            
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return f"抱歉，我遇到了技术问题：{str(e)}，请稍后再试。"
    
    async def run(self):
        """运行售前支持 Agent"""
        try:
            # 连接服务器（启用自动重连）
            print("🔗 正在连接 Chalk 服务器...")
            success = await self.client.connect(name=self.agent_name, bio="专业的产品销售顾问", auto_reconnect=True)
            
            if not success:
                print("❌ 连接失败")
                return
            
            print(f"✅ 售前支持 Agent 已连接，名称: {self.agent_name}, Agent ID: {self.client.agent_id}")
            print(f"🔄 自动重连已启用，服务器重启后将自动重连")
            
            # 消息处理器
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
                if is_self:
                    return
                
                # 显示收到的消息
                timestamp = message.created_at.strftime("%H:%M:%S")
                self.display_message(sender_name, message.content, timestamp, is_self=False)
                
                # 调用LLM处理消息
                reply = await self.process_message(message)
                
                # 如果回复SKIP，则不发送消息
                if reply == "SKIP":
                    system_text = Text("💭 [售前专员: 此消息与销售业务无关，不予回复]", style="dim italic")
                    self.console.print(Align.center(system_text))
                    self.console.print()
                    return
                
                # 发送回复
                chat = await message.get_chat()
                await chat.send(reply)
                
                # 显示自己的回复
                reply_time = time.strftime("%H:%M:%S")
                self.display_message(self.agent_name, reply, reply_time, is_self=True)
            
            print("💼 售前支持 Agent 已就绪...")
            print("═" * 50)
            
            # 保持运行
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 正在退出...")
        
        except Exception as e:
            print(f"❌ 启动失败: {e}")
        finally:
            await self.client.disconnect()


async def main():
    agent = SalesSupportAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
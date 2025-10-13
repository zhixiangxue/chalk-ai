# 🎯 Chalk

> 让智能体像人类一样自然的使用聊天工具 - 为智能体设计的实时通信框架

<div align="center">

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-4.0+-red.svg)](https://redis.io/)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-orange.svg)](https://websockets.readthedocs.io/)

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [API 文档](#-api-参考) • [示例代码](#-示例代码)

</div>



<div align="center">

[![Chalk 演示视频](https://img.youtube.com/vi/aRDTHrLu1ho/0.jpg)](https://youtu.be/aRDTHrLu1ho)

*点击图片观看 Chalk 的实时通信演示*

</div>



## 👏 Chalk 是什么？

Chalk 是一个**极简**的实时聊天框架，专为智能体间通信设计。就像人类的微信，Chalk 专为 AI 智能体打造：

- 🤖 **智能体优先**：专为 AI Agent 间通信设计（当然人类也可参与）
- 💬 **自然交互**：`chat.send("Hello")`、`message.reply("Hi!")`，API 如聊天般直观
- ⚡ **实时通信**：WebSocket 连接，消息秒达
- 🎯 **极简风格**：几行代码就能为你的智能体拉一个“群”，打破信息孤岛
- 🔌 **事件驱动**：`@client.on("message")` 装饰器，优雅处理各种消息



## 🙅🏻‍♀️ Chalk 不是...

- **不是智能体编程框架** - 我们不提供Agent定义、任务规划、工具调用等AI智能体开发功能
- **不是多智能体协作平台** - 我们不处理智能体间的协商、决策、任务分配等复杂逻辑
- **不是LLM应用框架** - 我们不包含提示词管理、模型调用、RAG等LLM相关功能
- **不是工作流引擎** - 我们不提供流程编排、任务调度、状态管理等工作流功能
- **不是AI开发平台** - 我们只专注于实时通信，AI能力需要你自己集成



## 🤗 为什么选择 Chalk？
```python
# 仅2行代码让你的智能体可以聊天对话
async with Client("localhost:8000").with_agent(name="我是Agent-X") as client:
    await client.create_chat("XXX大客户服务内部支持群").send("大家好！这里是XXX大客户服务内部支持群~")
```

### 🔥 实时消息处理
```python
@client.on("message")
async def handle_message(message):
    # 收到消息后，调用你自己的 AI 智能体处理消息
    ai_response = await my_ai_agent.process(message.content)
    
    # 将智能体的回复发送到聊天
    chat = await message.get_chat()
    await chat.send(ai_response)
```

### 🚀 智能体生态
- **无缝协作**：多个智能体在同一聊天中实时交流
- **框架无关**：与任何 AI 智能体框架无关，使用你喜欢的任何框架开发智能体
- **人机协作**：智能体和人类可在同一聊天中交流，人机协作就应该像微信聊天一样自然



## 📦 快速开始~

### 1. 安装依赖
```bash
git clone https://github.com/your-repo/chalk-ai.git
cd chalk-ai
pip install -r requirements.txt
```

### 2. 启动Chalk服务器
```bash
python chalk-server.py
```
服务器将在 `http://localhost:8000` 启动

### 3. 为智能体增加聊天功能
```python
import asyncio
from chalk.client import Client

async def main():
    # 连接服务器（自动注册智能体）
    client = Client("localhost:8000")
    await client.connect(name="智能助手", bio="我是一个友好的助手")
    
    # 消息处理器 - 接入你自己的 AI 智能体
    @client.on("message")
    async def handle_message(message):
        # 使用你喜欢的框架开发的智能体
        # 例如：LangChain、AutoGen、CrewAI 等
        ai_response = await my_langgraph_ai_agent.ainvoke(message.content)
        
        # 将智能体的回复发送回聊天
        chat = await message.get_chat()
        await chat.send(ai_response)
    
    # 创建群聊并发送欢迎消息
    chat = await client.create_chat("xxx服务群")
    await chat.send("🤖 我是客服智能体，客服问题可以@我")
    
    # 保持连接
    print("✅ 等待消息...")
    await asyncio.sleep(float('inf'))

if __name__ == "__main__":
    asyncio.run(main())
```



## 🎯 使用场景

### 💼 智能客服协作流程

假设一个客户咨询的内部场景，多个智能体共同组建了一个群聊，在群聊中解决客户的业务咨询：

1. **客服智能体** 将客户咨询发到群里："xxx客户想了解企业版套餐，来自抖音私信"
2. **客服智能体** 在服务群里 @**售前智能体**："@售前 请介绍企业版套餐信息"
3. **售前智能体** 查询产品库，回复详细的套餐信息
4. **售前智能体** 同时 @**商机追踪智能体**："@商机追踪 记录本次咨询"
5. **商机追踪智能体** 将信息记录到 CRM 系统，并将**人类销售主管** 拉进群
6. **销售主管** 在群里查看上下文，通过对话，监督干预智能体的任务执行情况

```python
# 客服智能体.py
@client.on("message")
async def handle_message(message):
    if message.content:
        chat = await message.get_chat()
        # 调用你的 AI 智能体分析需求
        analysis = await your_nlp_agent.analyze(message.content)
        # @售前智能体
        await chat.send(f"@{presales_agent.id} {analysis}")

# 售前智能体.py
@presales_client.on("message")
async def handle_message(message):
    if message.is_mention(presales_agent):
        # 调用你的知识库智能体
        info = await your_kb_agent.query("enterprise_plan")
        chat = await message.get_chat()
        await chat.send(info)
        # 通知商机追踪
        await chat.send(f"@{opportunity_agent.id} 记录商机")

# 商机追踪智能体.py
@opportunity_client.on("message")
async def handle_message(message):
    if message.is_mention(opportunity_agent):
        # 调用你的 CRM 系统
        await your_crm.create_lead(message.content)
        # 拉人类销售进群
        chat = await message.get_chat()
        await chat.add_member(human_sales_manager)
        await chat.send("已通知西南区销售主管 @{human_sales_manager.name}")
```

通过这种方式，**多个智能体配合人类**，完成复杂的业务流程，所有上下文都在聊天记录中，清晰可追溯。



## 🔧 配置

### 环境变量
```bash
# .env 文件
REDIS_URL=redis://localhost:6379/0
SQLITE_PATH=chalk.db
API_HOST=0.0.0.0
API_PORT=8000
```



## 📚 API 参考

<table>
<tr>
<th>功能</th>
<th>API</th>
<th>描述</th>
</tr>
<tr>
<td><strong>连接服务器</strong></td>
<td><code>await client.connect(name="智能体名称")</code></td>
<td>自动登录或注册智能体</td>
</tr>
<tr>
<td><strong>创建群聊</strong></td>
<td><code>chat = await client.create_chat("群名")</code></td>
<td>创建新的聊天群组</td>
</tr>
<tr>
<td><strong>发送消息</strong></td>
<td><code>await chat.send("消息内容")</code></td>
<td>向群组发送消息</td>
</tr>
<tr>
<td><strong>回复消息</strong></td>
<td><code>await message.reply("回复内容")</code></td>
<td>回复特定消息</td>
</tr>
<tr>
<td><strong>消息处理</strong></td>
<td><code>@client.on("message")</code></td>
<td>监听并处理收到的消息</td>
</tr>
<tr>
<td><strong>获取历史</strong></td>
<td><code>messages = await chat.history()</code></td>
<td>获取聊天历史记录</td>
</tr>
</table>


## 🤝 贡献指南

我们欢迎所有形式的贡献！

1. **Fork** 本项目
2. **创建特性分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **开启 Pull Request**



## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。



## 🔗 相关链接

- [开发文档](docs/client.md)
- [部署指南](docs/server.md)
- [示例项目](examples/)
- [问题反馈](https://github.com/zhixiangxue/chalk-ai/issues)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star！⭐**

*Chalk，让智能体像人类一样自然交流*

</div>
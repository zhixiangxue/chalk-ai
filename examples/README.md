# Chalk AI Examples - 示例

本目录包含三个Agent示例，演示如何使用Chalk让多个Agent像人类一样群聊协作。



## 🤓 前置准备

### 1. 启动服务器

详细步骤请参考：[服务器启动指南](../docs/server.md)

简要步骤：
```bash
# 启动Redis
redis-server

# 启动Chalk服务器
python chalk-server.py
```

### 2. 配置example所需的LLM

在 `examples/.env` 文件中配置OpenAI API（用于LLM功能）：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
```



## 🚀 快速开始

### 按顺序启动

**1. 启动客服Agent**
```bash
python examples/customer_service_agent.py
```
💡 记录输出的Agent ID，一会有用

**2. 启动售前Agent**
```bash
python examples/sales_support_agent.py
```
💡 记录输出的Agent ID，一会有用

**3. 启动人类控制台**
```bash
python examples/human_in_loop.py
```
💡根据提示输入前两个Agent的ID（用空格分隔），将他们加入群聊

### 🎉 看看发生了什么

现在你可以在人类控制台中：
- 发送消息与两个Agent互动
- 观察Agent根据专业领域智能回复
- 体验多Agent协作场景

输入 `/quit` 退出控制台。

## 示例说明

| 文件 | 说明 |
|------|------|
| `customer_service_agent.py` | 客服Agent，处理技术支持和售后问题 |
| `sales_support_agent.py` | 售前Agent，处理销售和商务咨询 |
| `human_in_loop.py` | 人类交互控制台，创建群组并邀请Agent |
| `rich_message_sample.py` | Rich库消息渲染效果演示 |



## 🐛 故障排除

### 常见问题

**Q: Agent连接失败？**
A: 检查Chalk服务器是否启动，端口是否正确

**Q: LangChain回复异常？**  
A: 检查OPENAI_API_KEY是否正确设置，网络是否通畅

**Q: 管理看板显示异常？**
A: 确保终端支持ANSI色彩，Windows用户可安装colorama

**Q: Agent重复创建？**
A: 使用相同名称会创建失败，可以使用现有Agent ID连接



## 😎 开始为你的智能体构建聊天群吧，让它们像人类一样合作沟通~
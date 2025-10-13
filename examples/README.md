# Chalk AI Examples - 示例集合

这个目录包含了 Chalk AI 的使用示例，展示如何构建智能化的AI Agent系统。

## 📋 示例列表

### 1. 客户服务Agent (`customer_service_agent.py`)
**功能特性：**
- 🔗 自动接入Chalk平台并显示Agent ID
- 🎉 加入群组后自动发送欢迎消息（延迟几秒）
- 🤖 基于LangChain的智能客服系统
- 💬 自动回复用户咨询，提供企业版功能介绍
- 🛠️ 支持产品功能查询、技术支持、问题解答

### 2. 售前支持Agent (`sales_support_agent.py`)
**功能特性：**
- 🔗 自动接入Chalk平台并显示Agent ID  
- 💼 基于LangChain的专业销售顾问
- 💰 提供产品定价、方案推荐、ROI计算
- 🆚 竞品对比分析和优势展示
- 🎬 演示安排和试用申请

### 3. 管理看板 (`management_dashboard.py`)
**功能特性：**
- 🏗️ 创建演示聊天群组
- 👥 邀请指定Agent加入群组
- 📊 实时监控聊天活动和Agent状态
- 💬 管理员异步发送消息
- 🎛️ 可视化管理界面

## # Examples 快速开始

本目录包含三个Agent示例，演示如何使用Chalk构建多Agent协作系统。

## 前置准备

### 1. 启动服务器

详细步骤请参考：[服务器启动指南](../docs/server.md)

简要步骤：
```bash
# 启动Redis
redis-server

# 启动Chalk服务器
python chalk-server.py
```

### 2. 配置环境变量

在 `examples/.env` 文件中配置OpenAI API（用于LLM功能）：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选
OPENAI_MODEL=gpt-3.5-turbo  # 可选
```

## 运行示例

### 启动顺序

**1. 启动客服Agent**
```bash
python examples/customer_service_agent.py
```
记录输出的Agent ID

**2. 启动售前Agent**
```bash
python examples/sales_support_agent.py
```
记录输出的Agent ID

**3. 启动人类控制台**
```bash
python examples/human_in_loop.py
```
根据提示输入前两个Agent的ID（用空格分隔）

### 开始体验

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

## 🚀 快速开始

### 环境准备

1. **安装依赖**
```bash
# 确保在虚拟环境中
pip install -r requirements.txt
```

2. **启动Chalk服务器**
```bash
python chalk-server.py
```

3. **配置环境变量（可选）**
```bash
# 设置OpenAI API Key以获得更智能的回复
export OPENAI_API_KEY=your_openai_api_key_here
```

### 使用步骤

#### 步骤1：启动Agent们

**终端1 - 启动客户服务Agent：**
```bash
cd examples
python customer_service_agent.py
```

**终端2 - 启动售前支持Agent：**
```bash
cd examples  
python sales_support_agent.py
```

#### 步骤2：启动管理看板

**终端3 - 启动管理看板：**
```bash
cd examples
python management_dashboard.py
```

#### 步骤3：操作演示

1. **创建群组**：管理看板会自动创建演示群组
2. **邀请Agent**：输入Agent ID列表，或使用`/invite <agent_id>`命令
3. **开始聊天**：在管理看板中输入消息，观察Agent的智能回复
4. **监控状态**：看板会实时显示Agent活跃度和消息统计

## 💡 使用示例

### 测试客户服务Agent

在管理看板中发送以下消息来测试客服功能：

```
你好，我想了解一下企业版有什么功能？
我们公司遇到登录问题，怎么解决？
你们的产品和微信企业版比有什么优势？
```

### 测试售前支持Agent  

发送以下消息来测试销售功能：

```
我们是500人的公司，需要什么方案？
你们的价格怎么样？有优惠吗？
能安排个产品演示吗？
和竞品比你们有什么优势？
```

## 🔧 高级配置

### LangChain集成

如果设置了`OPENAI_API_KEY`，Agent会使用LangChain提供更智能的回复：

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."

# Linux/Mac
export OPENAI_API_KEY="sk-..."
```

### 自定义Agent行为

可以通过修改以下部分来定制Agent：

1. **修改Agent人格**：调整`setup_llm()`中的system prompt
2. **添加工具**：在`tools`列表中添加新的LangChain工具
3. **自定义回复**：修改`_simple_reply()`中的规则回复逻辑

### 管理看板定制

可以自定义看板功能：

1. **修改刷新频率**：调整`print_dashboard()`中的`asyncio.sleep(5)`
2. **添加新命令**：在`handle_command()`中添加新的斜杠命令
3. **自定义统计**：扩展`show_detailed_stats()`中的统计指标

## 🎯 实际应用场景

### 企业客服系统
- 部署客户服务Agent处理常见问题
- 7x24小时自动回复客户咨询
- 无缝转接到人工客服

### 销售支持平台
- 售前支持Agent协助销售团队
- 自动化产品介绍和方案推荐
- 潜在客户培育和跟进

### 内部协作助手
- 多个专业Agent协作处理复杂任务
- 知识库查询和信息整合
- 工作流程自动化

## ⚠️ 注意事项

1. **虚拟环境**：请确保在虚拟环境中运行，遵循项目规范
2. **服务器连接**：确保Chalk服务器正在运行且可访问
3. **Agent ID**：保存好Agent ID，重启后可复用现有Agent
4. **资源清理**：使用Ctrl+C或`/quit`命令正确退出程序

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

### 调试技巧

1. **启用详细日志**：在LangChain Agent中设置`verbose=True`
2. **检查连接状态**：观察控制台的连接确认信息
3. **监控WebSocket**：查看消息收发是否正常

## 📚 扩展阅读

- [Chalk AI 客户端API文档](../README.md)
- [LangChain官方文档](https://python.langchain.com/)
- [WebSocket消息协议](../docs/)

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这些示例！
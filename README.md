<div align="center">
<a href="https://youtube.com/watch?v=xOKQ7EQcggw"><img src="https://raw.githubusercontent.com/zhixiangxue/chalk-ai/main/docs/assets/logo.png" alt="Demo Video" width="120"></a>

**A minimalist real-time messaging service.**

Chalk is a lightweight messaging service built on WebSocket. It provides group chats, direct messages, and real-time event delivery - nothing more, nothing less.

</div>

---

## What is Chalk?

Chalk is a **messaging service**,  Think of it as a simple, self-hosted alternative to Slack or Discord, designed for programmatic use.

**What Chalk provides:**
- Real-time messaging via WebSocket
- Group chats and direct messages
- Message history and persistence
- Event-driven message handling
- User authentication

**What Chalk does NOT provide:**
- AI/LLM capabilities
- Agent orchestration
- Task scheduling
- Business logic

Chalk is infrastructure. You build whatever you want on top of it.

---

## Core Features

### Minimalist API

Start a server in 2 lines, connect a client in 3:

```python
# Server
from chalk.server import ChalkServer

server = ChalkServer(
    redis_url="redis://localhost:6379",  # Redis for pub/sub
    db_path="chalk.db",                   # SQLite for data persistence
    host="0.0.0.0",                       # Listen on all interfaces
    port=8000                              # Server port
)
server.run()
```

```python
# Client
from chalk.client import Client

alice = Client(
    name="alice",
    password="password123",
    server="localhost:8000"  # Server address
)
chat = await alice.create_group_chat("My Chat")
await chat.send("Hello!")
```

### Real-Time Messaging

- **WebSocket-based**: Instant bidirectional communication
- **Event-driven**: React to messages with decorators
- **Persistent**: Full message history in SQLite
- **Reliable**: Auto-reconnect on network issues

### Group & Direct Chats

- **Group chats**: Multi-party conversations, unlimited members
- **Direct messages**: 1-on-1 private chats
- **Message history**: Query past messages anytime
- **Member management**: Add/remove members dynamically

---

## Quick Start

### Installation

```bash
pip install chalks
```

### 1. Start the Server

```python
from chalk.server import ChalkServer

server = ChalkServer(
    redis_url="redis://localhost:6379",  # Redis for pub/sub
    db_path="chalk.db"                    # SQLite for data persistence
)
server.run()
```

**Prerequisites:**
- Redis must be running: `redis-server`

### 2. Send Your First Message

```python
import asyncio
from chalk.client import Client

async def main():
    # Create client
    alice = Client("alice", "password123")
    
    # Create a group chat
    chat = await alice.create_group_chat("My First Chat")
    await chat.send("Hello world!")
    
    print(f"Chat created: {chat.id}")

asyncio.run(main())
```

### 3. Receive Messages

```python
# Bob joins the same chat
bob = Client("bob", "password456")

# Register message handler
@bob.on("message")
async def handle_message(msg):
    print(f"{msg.sender.name}: {msg.content}")

# Join Alice's chat
await bob.join_chat(chat.id)

# Bob receives all messages in real-time
await asyncio.Event().wait()
```

---

## Core Concepts

### Client

Represents a user or agent in the system:

```python
alice = Client(
    name="alice",           # Username
    password="pass123",     # Password (auto-registers if new)
    bio="AI assistant",     # Optional bio
    server="localhost:8000"  # Server address
)
```

### Chat

Two types of chats:

**Group Chat** - Multi-party conversations:
```python
# Create group
chat = await alice.create_group_chat("Team Chat")

# Add members
await chat.add_member(bob_id)
await chat.add_member(charlie_id)

# Multiple members can join
```

**Direct Chat** - 1-on-1 conversations:
```python
# Create direct chat with Bob
dm = await alice.create_direct_chat(bob_id)
```

### Message

Messages with rich metadata:

```python
@client.on("message")
async def handle(msg):
    print(f"From: {msg.sender.name}")
    print(f"Content: {msg.content}")
    print(f"Time: {msg.timestamp}")
    
    # Reply to message
    await msg.reply("Got it!")
    
    # Get chat context
    chat = await msg.get_chat()
    members = await chat.get_members()
```

---

## Common Patterns

### Chat Management

```python
# List all chats
chats = await client.list_chats()

# Filter by type
group_chats = [c for c in chats if c.is_group()]
direct_chats = [c for c in chats if c.is_direct()]

# Get chat details
chat = await client.get_chat(chat_id)
members = await chat.get_members()
messages = await chat.get_messages(limit=50)

# Join/leave
await client.join_chat(chat_id)
await client.leave_chat(chat_id)
```

---

## API Reference

### Client Methods

| Method | Description |
|--------|-------------|
| `create_group_chat(name, members=[])` | Create a group chat |
| `create_direct_chat(user_id)` | Create/get 1-on-1 chat |
| `list_chats()` | List all chats |
| `get_chat(chat_id)` | Get chat details |
| `join_chat(chat_id)` | Join a chat |
| `whois(username)` | Find users by name |
| `stop()` | Disconnect client |

### Chat Methods

| Method | Description |
|--------|-------------|
| `send(content)` | Send a message |
| `get_messages(limit=50)` | Get message history |
| `get_members()` | Get chat members |
| `is_group()` | Check if group chat |
| `is_direct()` | Check if direct chat |

### Message Methods

| Method | Description |
|--------|-------------|
| `reply(content)` | Reply to this message |
| `get_chat()` | Get the chat this message belongs to |
| `get_sender()` | Get sender details |

---

## Examples

comming soon...

---

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Agent/Human    │         │  Agent/Human    │
│  (Client SDK)   │         │  (Client SDK)   │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │      WebSocket + HTTP     │
         │                           │
         └───────────┬───────────────┘
                     │
         ┌───────────▼────────────┐
         │   Chalk Server         │
         │  (FastAPI + WebSocket) │
         └───────────┬────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼────┐
    │  Redis   │          │ SQLite   │
    │ (Pub/Sub)│          │  (Data)  │
    └──────────┘          └──────────┘
```

**Tech Stack:**
- **Server**: FastAPI + Uvicorn
- **Real-time**: WebSocket + Redis Pub/Sub
- **Storage**: SQLite (Peewee ORM)
- **Client**: httpx + websockets
- **Tasks**: Huey (async task queue)

---

## Is Chalk for You?

Use Chalk if you need:

- **Real-time messaging infrastructure** without the bloat
- **WebSocket-based communication** that's easy to integrate
- **Self-hosted messaging** (no third-party dependencies)
- **Simple API** that gets out of your way
- **Group chats and DMs** with message persistence

Chalk does one thing: **messaging**. It does it well.

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions welcome! Please open an issue or PR.

---

<div align="right">

**Built with ❤️ for the AI agent community**

<a href="https://youtube.com/watch?v=xOKQ7EQcggw"><img src="https://raw.githubusercontent.com/zhixiangxue/chalk-ai/main/docs/assets/logo.png" alt="Demo Video" width="120"></a>

</div>

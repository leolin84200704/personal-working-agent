# LIS Code Agent v2.0

> AI-powered agent for Jira ticket processing and code management with RAG-based memory and true conversational interface.

## What's New in v2.0

- **🔄 Markdown-Driven Architecture** - OpenClaw-style skill definitions in `.md` files
- **🧠 LLM-Guided Execution** - Agent reads skills and consults LLM on how to execute
- **💬 True Conversational Interface** - No special commands needed, just chat naturally
- **🧠 RAG Memory System** - Vector-based semantic search for relevant memories
- **📝 Auto-Learning** - Automatically updates SOUL/IDENTITY/USER/MEMORY.md from conversations
- **⚡ Incremental Code Editing** - Smart code modifications, not full file replacement
- **🔒 Thread-Safe Git Operations** - Concurrent-safe operations with proper locking

## Markdown-Driven Architecture

This agent uses an **OpenClaw-style markdown-driven architecture**:

### Core Concept
- **Skills stored in `.md` files** - Execution logic is configuration, not code
- **Agent reads markdown** - The agent loads skill definitions from markdown
- **LLM determines execution** - Agent consults LLM with skill content to create plans
- **Only code for interfaces** - Scripts and APIs are code; everything else is markdown

### Key Files

```
lis-code-agent/
├── skills/                    # Skill definitions (markdown-driven)
│   ├── emr-integration/
│   │   └── SKILL.md          # EMR Integration ticket handling
│   ├── database/
│   └── git/
├── TOOLS.md                   # Available tools (scripts, APIs)
├── AGENTS.md                  # Agent type definitions
├── SOUL.md                    # Core philosophy & business rules
├── IDENTITY.md                # Agent role & capabilities
└── MEMORY.md                  # Accumulated knowledge
```

### How It Works

1. **User says**: "執行 VP-15979"
2. **Agent loads skill**: Reads `skills/emr-integration/SKILL.md`
3. **Agent loads tools**: Reads `TOOLS.md` for available scripts
4. **LLM creates plan**: Analyzes ticket + skill + tools → creates JSON plan
5. **Agent executes**: Runs the plan using the tools
6. **Agent outputs**: Shows full reasoning and execution results

### Adding New Skills

To add a new capability:

1. Create `skills/your-skill/SKILL.md`:
   ```markdown
   # Your Skill Name

   ## Metadata
   ```yaml
   name: your-skill
   type: database
   agent: emr-integration-agent
   ```

   ## Purpose
   Describe what this skill does...

   ## Execution Flow
   Step-by-step instructions...

   ## Business Rules
   Critical rules to follow...
   ```

2. Update `TOOLS.md` if you need new tools
3. Update `AGENTS.md` if you need a new agent type
4. The agent will automatically discover and use your skill!

## Architecture

```
lis-code-agent/
├── src/
│   ├── agent/              # Agent Loop (Observe → Think → Act → Learn)
│   │   ├── loop.py         # Core agent orchestration
│   │   ├── state.py        # Conversation state management
│   │   └── memory_bank.py  # Memory integration
│   ├── api/                # FastAPI service
│   │   ├── main.py         # Application entry point
│   │   ├── routes/
│   │   │   ├── chat.py     # WebSocket endpoint
│   │   │   └── control.py  # REST control endpoints
│   │   └── schemas.py      # Pydantic models
│   ├── skills/             # Agent capabilities
│   │   ├── base.py         # Base skill class
│   │   ├── jira_skill.py   # Jira operations
│   │   ├── git_skill.py    # Git operations
│   │   ├── code_skill.py   # Code editing
│   │   └── memory_skill.py # Memory management
│   ├── memory/             # Memory system
│   │   ├── vector_store.py # ChromaDB vector store
│   │   ├── auto_update.py  # Auto memory updates
│   │   └── manager.py      # MD file management
│   ├── integrations/       # External integrations
│   │   ├── jira.py         # Jira API client
│   │   └── git_operator.py # Thread-safe Git operations
│   ├── utils/              # Utilities
│   │   ├── logger.py       # Logging
│   │   └── prompt.py       # Prompt templates
│   └── config.py           # Configuration management
├── storage/               # Persistent storage
│   ├── chroma/            # Vector database
│   └── conversations/     # Conversation history
├── SOUL.md                # Agent core philosophy
├── IDENTITY.md            # Agent role and capabilities
├── USER.md                # User preferences
├── MEMORY.md              # Accumulated knowledge
└── requirements.txt
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Claude API
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://api.anthropic.com  # Optional: for proxy

# Jira
JIRA_SERVER=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your_token_here

# Git
GIT_USER_NAME="LIS Code Agent"
GIT_USER_EMAIL="lis-code-agent@local"

# Paths
REPOS_BASE_PATH=/Users/yourname/src
```

## Usage

### Starting the Service

```bash
# Start the agent service
python start_agent.py

# Or with uvicorn directly
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The service will be available at:
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/api/ws/chat

### Using the Agent

#### Option 1: WebSocket Client

```bash
python test_client.py
```

#### Option 2: Direct Python

```python
import asyncio
from src.agent.loop import AgentLoop

async def chat():
    agent = AgentLoop()
    response = await agent.process_message("幫我看看 LIS-123 這個 ticket")
    print(response["response"])

asyncio.run(chat())
```

#### Option 3: Interactive API Docs

Visit http://localhost:8000/docs for interactive API documentation.

## Example Conversations

```
You: 幫我掃描一下有哪些新的 Jira tickets
Agent: Found 10 tickets:
  • VP-15948: Repush Charm results (Dev To Do)
  • VIB-1670: Add provider firstname... (Dev To Do)
  ...

You: 分析一下 VP-15948
Agent: [Analyzes ticket and provides detailed breakdown]

You: 幫我在 LIS-transformer 裡修改 hl7_parser.py
Agent: [Understands context, locates file, makes smart edits]
```

## Memory System

The agent learns from every conversation:

- **SOUL.md**: Core philosophy, behavioral guidelines, branch naming
- **IDENTITY.md**: Role, capabilities, repository information
- **USER.md**: Your preferences and work patterns
- **MEMORY.md**: Q&A, patterns, gotchas, repository knowledge

Memory is automatically updated during conversations using Claude to extract learnings.

## API Endpoints

### WebSocket
- `ws://localhost:8000/api/ws/chat` - Real-time conversation

### REST
- `GET /` - Service info
- `GET /health` - Health check
- `GET /api/memory/{file_type}` - Get memory content
- `GET /api/stats` - Service statistics
- `POST /api/memory/update` - Manual memory update
- `POST /api/reset` - Reset conversation

## Security

Git operations are strictly controlled:
- ✅ Allowed: `feature/leo/*`, `bugfix/leo/*` branches
- ✅ Push only to own branches
- ❌ Blocked: force push, reset --hard, direct main/master push
- 🔒 Thread-safe with repository-level locking

## Development

### Testing

```bash
# Test core functionality
python test_agent.py

# Test WebSocket client
python test_client.py

# Run with coverage
pytest
```

### Project Status

This is an internal tool for Leo's LIS-related projects.

## License

Internal use only.

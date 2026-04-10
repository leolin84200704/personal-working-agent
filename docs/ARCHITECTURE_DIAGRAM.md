# Agent Architecture Evolution

## Visual Comparison

### Before: Hardcoded Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    prompt_interactive.py                    │
│                     (500+ lines)                            │
├─────────────────────────────────────────────────────────────┤
│  _execute_db_operations():                                 │
│  ├─ _llm_analyze_ticket()      [Hardcoded analysis]       │
│  ├─ _get_customer_from_rpc()    [Hardcoded RPC call]      │
│  ├─ _check_db_state()          [Hardcoded DB check]       │
│  ├─ _compare_data()            [Hardcoded comparison]     │
│  └─ _execute_operations()       [Hardcoded execution]      │
│                                                              │
│  ❌ Business rules in Python code                           │
│  ❌ Changing behavior = code change                         │
│  ❌ Logic scattered across functions                       │
└─────────────────────────────────────────────────────────────┘
```

### After: Markdown-Driven Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                         Markdown Files                           │
│                  (Human-Readable Behavior)                       │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │  SKILL.md   │  │  TOOLS.md    │  │   MEMORY.md/SOUL.md │    │
│  │             │  │              │  │                     │    │
│  │ • Purpose   │  │ • Available  │  │ • Learned patterns  │    │
│  │ • Rules     │  │   scripts    │  │ • Gotchas          │    │
│  │ • Flow      │  │ • APIs       │  │ • Examples         │    │
│  │ • Examples  │  │ • gRPC       │  │ • Core philosophy  │    │
│  └─────────────┘  └──────────────┘  └─────────────────────┘    │
│         │                 │                     │                │
│         └─────────────────┴─────────────────────┘                │
│                           │                                      │
│                           ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              SkillLoader (Python)                         │  │
│  │        - Reads markdown files                            │  │
│  │        - Parses sections                                  │  │
│  │        - Returns structured Skill objects                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           │                                      │
│                           ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          MarkdownExecutor (Python)                        │  │
│  │                                                             │  │
│  │  1. Load skill from SKILL.md                              │  │
│  │  2. Pass skill + ticket to LLM                            │  │
│  │  3. LLM creates structured plan (JSON)                    │  │
│  │  4. Execute the plan using TOOLS                          │  │
│  │  5. Return results                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ✅ Business rules in markdown                                 │
│  ✅ Changing behavior = edit markdown file                     │
│  ✅ Logic centralized in skills                               │
└───────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌──────────────┐
│   User:      │
│ "執行 VP-15791"│
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    MarkdownExecutor                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 1: Load Skill                                  │   │
│  │   - Read skills/emr-integration/SKILL.md            │   │
│  │   - Read TOOLS.md                                   │   │
│  │   - Read SOUL.md                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 2: LLM Analysis (with skill context)           │   │
│  │                                                      │   │
│  │  System Prompt:                                     │   │
│  │  - SKILL.md content (rules, flow, examples)         │   │
│  │  - TOOLS.md (available scripts)                     │   │
│  │  - MEMORY.md (learned patterns)                     │   │
│  │  - CRITICAL PATTERN DETECTION                       │   │
│  │                                                      │   │
│  │  User Prompt:                                       │   │
│  │  - Ticket description                               │   │
│  │  - Request for JSON plan                            │   │
│  │                                                      │   │
│  │  LLM Returns:                                       │   │
│  │  {                                                  │   │
│  │    "extracted_data": {...},                          │   │
│  │    "msh06_source": "practice_id",  ← Detected!      │   │
│  │    "actions": [...]                                  │   │
│  │  }                                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 3: Execute Plan                                │   │
│  │   - Call get-customer-rpc.ts                        │   │
│  │   - Call get-existing-data-json.ts                  │   │
│  │   - Compare data                                    │   │
│  │   - Call update scripts if needed                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 4: Output Results                              │   │
│  │   - Show full reasoning                             │   │
│  │   - Show extracted data                             │   │
│  │   - Show execution results                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│   User sees  │
│   results    │
└──────────────┘
```

## The Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                     Self-Iteration Cycle                       │
└─────────────────────────────────────────────────────────────────┘

                          ┌─────────────┐
                          │   User      │
                          │  Feedback   │
                          └──────┬──────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
  ┌─────────────┐       ┌───────────────┐       ┌─────────────┐
  │ Update      │       │ Update        │       │ Update      │
  │ SKILL.md    │       │ MEMORY.md     │       │ Prompts     │
  │             │       │               │       │ (highlight) │
  │ - Add       │       │ - Add         │       │ - Emphasize │
  │   pattern   │       │   examples    │       │   critical  │
  │   examples  │       │ - Document    │       │   sections  │
  └──────┬──────┘       │   learning   │       └──────┬──────┘
         │               └───────┬───────┘              │
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │    Test     │
                          │             │
                          │ - Positive  │
                          │   examples  │
                          │ - Negative  │
                          │   examples  │
                          └──────┬──────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │   Verify    │
                          │             │
                          │ Agent now   │
                          │ handles     │
                          │ correctly?  │
                          └──────┬──────┘
                                 │
                    ┌────────────┴────────────┐
                    │ Yes                     │ No
                    ▼                         ▼
             ┌───────────┐           ┌──────────────┐
             │ Learning  │           │ Iterate      │
             │ Complete │           │ Again        │
             └───────────┘           └──────────────┘
```

## Auto-Learning Flow (Conversation-Based)

```
┌─────────────────────────────────────────────────────────────────┐
│                     User-Agent Conversation                     │
└─────────────────────────────────────────────────────────────────┘

                          ┌─────────────┐
                          │   User:     │
                          │ "你錯了，   │
                          │ Anna 在 3 個│
                          │ practices"  │
                          └──────┬──────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Response                           │
│                                                             │
│  1. Generate response via LLM                               │
│  2. Show response to user                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    🧠 Auto-Learner                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 1: Detect Correction                            │   │
│  │   - Check for correction indicators                  │   │
│  │   - "錯了", "wrong", "missing", "應該是"              │   │
│  │   - Returns: True if correction detected             │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 2: Extract Learning (via LLM)                  │   │
│  │                                                      │   │
│  │  Input: user_message + agent_response + context     │   │
│  │  Output: JSON with learning structure               │   │
│  │                                                      │   │
│  │  {                                                  │   │
│  │    "category": "gotcha",                            │   │
│  │    "title": "Multi-Practice Provider",              │   │
│  │    "problem": "Agent missed that...",               │   │
│  │    "solution": "Each (provider, practice) = record" │   │
│  │    "files_to_update": ["MEMORY.md"]                 │   │
│  │  }                                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 3: Apply Learning                               │   │
│  │                                                      │   │
│  │   Based on category:                                 │   │
│  │   - "gotcha" → MemoryManager.learn_gotcha()        │   │
│  │   - "pattern" → MemoryManager.learn_gotcha()       │   │
│  │   - "ms-rule" → Update SKILL.md                     │   │
│  │                                                      │   │
│  │   Writes to: MEMORY.md, SKILL.md                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Step 4: Show Learning to User                        │   │
│  │                                                      │   │
│  │   ┌─────────────────────────────────────────────┐   │   │
│  │   │ 🧠 Auto-Learning                              │   │   │
│  │   │ ├─ Learned: Multi-Practice Provider          │   │   │
│  │   │ └─ Updated: MEMORY.md                          │   │   │
│  │   └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────┐
                    │  Continue Conversation  │
                    │  (Agent now knows more)  │
                    └─────────────────────────┘
```

### Key Components

```
src/memory/
├── manager.py          # MemoryManager
│   └── learn_gotcha()  # Write to MEMORY.md
│
└── auto_learner.py     # AutoLearner (NEW)
    ├── _detect_correction()     # Check if user is correcting
    ├── _extract_learning()      # LLM extracts structured learning
    └── _apply_learning()        # Write to .md files
```

### Integration Point

```python
# In prompt_interactive.py - after every LLM response

answer = response.content[0].text
console.print(Panel(answer, ...))

# NEW: Auto-learn from feedback
learning_result = await auto_learner.learn_from_feedback(
    user_input=user_message,
    agent_response=answer,
    context=context
)

if learning_result["learned"]:
    console.print(Panel("🧠 Learned: ...", title="Auto-Learning"))
```

---

## File Structure Overview

```
lis-code-agent/
│
├── 📄 SOUL.md                    # Core philosophy & business rules
├── 📄 IDENTITY.md                # Agent role & capabilities
├── 📄 MEMORY.md                  # Learned patterns & gotchas
├── 📄 TOOLS.md                   # Available tools/scripts
├── 📄 AGENTS.md                  # Agent type definitions
│
├── 📁 skills/                    # ← SKILLS LIVE HERE (not code!)
│   ├── emr-integration/
│   │   └── SKILL.md             # EMR Integration behavior
│   ├── database/
│   │   └── SKILL.md             # Database operations
│   └── git/
│       └── SKILL.md             # Git operations
│
├── 📁 src/                       # ← ONLY INTERFACES HERE
│   ├── skills/
│   │   └── loader.py            # Reads markdown skills
│   └── core/
│       └── markdown_executor.py # Executes based on markdown
│
└── 📁 docs/
    ├── AGENT_SELF_ITERATION_GUIDE.md
    └── ARCHITECTURE_DIAGRAM.md   # This file
```

## Key Insight

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   BEFORE: Code determines behavior                           │
│   ────────────────────────────────                          │
│   To change behavior → Edit Python code                      │
│                                                             │
│   AFTER: Markdown determines behavior                        │
│   ─────────────────────────────────                          │
│   To change behavior → Edit markdown file                    │
│                                                             │
│   The LLM reads markdown and decides how to execute          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*Created: 2026-04-07*

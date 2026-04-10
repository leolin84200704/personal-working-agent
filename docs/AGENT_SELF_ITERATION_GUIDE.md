# AI Agent Self-Iteration Guide

> Documenting the journey of building a self-improving AI agent, from hardcoded logic to markdown-driven architecture.

---

## Table of Contents

1. [Overview](#overview)
2. [Initial Architecture (Before)](#initial-architecture-before)
3. [Problems Identified](#problems-identified)
4. [Iteration 1: From Hardcoded to Data-Driven](#iteration-1-from-hardcoded-to-data-driven)
5. [Iteration 2: From Code to Markdown](#iteration-2-from-code-to-markdown)
6. [Iteration 3: Learning from Feedback](#iteration-3-learning-from-feedback)
7. [Iteration 4: Automatic Learning from Conversation](#iteration-4-automatic-learning-from-conversation)
8. [Principles of Self-Iteration](#principles-of-self-iteration)
9. [Patterns for Agent Evolution](#patterns-for-agent-evolution)
10. [Checklist for Creating Self-Iterating Agents](#checklist-for-creating-self-iterating-agents)
11. [Implementing Auto-Learner](#implementing-auto-learner)

---

## Overview

This document captures the journey of transforming the LIS Code Agent from a hardcoded Python script executor into a markdown-driven, self-improving agent. The key insight is that **agents should evolve from code-based to configuration-based**, with LLMs interpreting the configuration rather than executing hardcoded logic.

### The Core Philosophy

> **"Don't write what you can configure. Don't configure what you can document."**

A self-iterating agent should:
1. Store execution logic in **human-readable markdown**
2. Use LLMs to **interpret and execute** based on that markdown
3. **Learn from feedback** by updating the markdown
4. Require **minimal code changes** to add new capabilities

---

## Initial Architecture (Before)

### What We Started With

```python
# prompt_interactive.py - ~500 lines of hardcoded logic
def _execute_db_operations(self, ticket, analysis):
    results = []

    # Step 1: Hardcoded analysis
    thinking_result = self._llm_analyze_ticket(ticket)
    provider_id = thinking_result.get('provider_id')
    # ... 50+ lines of extraction logic

    # Step 2: Hardcoded gRPC call
    if grpc_needed:
        rpc_data = self._get_customer_from_rpc(customer_id, practice_id)
        # ... 30+ lines of RPC handling

    # Step 3: Hardcoded comparison
    if existing_ehr:
        # ... 40+ lines of comparison logic

    # Step 4: Hardcoded execution
    for attempt in range(max_retries):
        # ... 80+ lines of execution logic

    return "\n".join(results)
```

### Problems with This Approach

| Problem | Impact |
|---------|--------|
| **Hardcoded business rules** | Changing behavior requires code changes |
| **Scattered logic** | Rules embedded across 500+ lines of Python |
| **No transparency** | Can't see what the agent will do without reading code |
| **Hard to train** | Learning from feedback means rewriting code |
| **Not self-documenting** | Logic separated from documentation |

---

## Problems Identified

### Problem 1: Agent Not Detecting Critical Patterns

**Symptom:**
```
User: "為什麼msh06_receiving_facility 是用clinic_id?
請你直接看這兩個ticket,除非ticket有提到否則是用customer_id最為MSH06"
```

**Root Cause:**
The LLM prompt didn't emphasize checking for "MSH value is the Practice ID" pattern.

**The Learning:**
> **Critical patterns must be EXPLICITLY documented and HIGHLIGHTED in prompts.**

### Problem 2: Wrong Default Behavior

**Symptom:**
```
Ticket VP-15979: No MSH mention → Should use customer_id
But agent used practice_id (wrong)
```

**Root Cause:**
Default behavior wasn't clearly defined in the prompt.

**The Learning:**
> **Always define DEFAULT behavior and EXCEPTIONS explicitly.**

### Problem 3: Architecture Didn't Support Easy Updates

**Symptom:**
```
User: "你改的這個code還是一樣讓他跑code而不是存成 md 然後去諮詢LLM,
和我預期的最終目標不符合啊請你參考openclaw"
```

**Root Cause:**
Execution logic was in Python, not in markdown.

**The Learning:**
> **Separate INTERFACE (code) from BEHAVIOR (markdown).**

---

## Iteration 1: From Hardcoded to Data-Driven

### Changes Made

**Before:**
```python
# Hardcoded extraction
provider_id = thinking_result.get('provider_id')
practice_id = thinking_result.get('practice_id')
```

**After:**
```python
# LLM creates structured plan
plan = {
    "extracted_data": {
        "provider_id": "...",
        "practice_id": "...",
        "msh06_source": "customer_id" or "practice_id"
    },
    "actions": [...]
}
```

### Key Insight

> **Let the LLM create a structured plan, then execute that plan.**

This separates:
1. **Planning** (LLM + Context) → Creates JSON plan
2. **Execution** (Code) → Follows the plan

---

## Iteration 2: From Code to Markdown

### The OpenClaw Pattern

After studying openclaw's architecture, we adopted:

```
lis-code-agent/
├── skills/                    # ← Behavior lives here (markdown)
│   ├── emr-integration/
│   │   └── SKILL.md          # ← All logic for this skill
│   ├── database/SKILL.md
│   └── git/SKILL.md
├── TOOLS.md                   # ← Available tools
├── AGENTS.md                  # ← Agent definitions
└── SOUL.md                    # ← Core philosophy
```

### The Skill Loader

```python
class SkillLoader:
    """Load skills from markdown files."""

    def get_skill(self, name: str) -> Skill:
        """Load a skill by name."""

    def get_section(self, skill: Skill, section: str) -> str:
        """Extract a section from the skill markdown."""
```

### The Markdown Executor

```python
class MarkdownExecutor:
    """Execute based on markdown skill definitions."""

    def execute_emr_integration(self, ticket):
        # 1. Load skill from SKILL.md
        skill = self.skill_loader.get_skill("emr-integration")

        # 2. LLM reads skill + creates plan
        analysis = self._llm_analyze_with_skill(ticket, skill, ...)

        # 3. Execute the plan
        return self._execute_plan(ticket, analysis)
```

### Key Insight

> **Skills are configuration in markdown, not code in Python.**

When you need to change behavior:
1. Edit the `.md` file
2. No code changes needed
3. Agent automatically uses new behavior

---

## Iteration 3: Learning from Feedback

### The Feedback Loop

```
User Feedback
    ↓
Identify the Gap
    ↓
Update Markdown (SKILL.md, SOUL.md, MEMORY.md)
    ↓
Update LLM Prompts (highlight the pattern)
    ↓
Test with Examples
    ↓
Verify Learning
```

### Example: MSH Pattern Detection

**Step 1: User Feedback**
```
"在VP-15791 有提到 MSH value is the Practice ID for this practice,
請你先幫我就這個ticket修正後train 該agent"
```

**Step 2: Identify the Gap**
- Agent wasn't detecting the "MSH value is the Practice ID" pattern
- Default behavior wasn't explicit

**Step 3: Update Markdown**

Added to `SKILL.md`:
```markdown
### Step 1: Analyze Ticket

**CRITICAL PATTERN DETECTION:**

Check if ticket says MSH value should be Practice ID. Look for:
- "MSH value is the Practice ID"
- "MSH value is the practice ID"
- "msh value is the practice id"
- "update all MSH values to practice ID"
- "use practice ID for MSH"

If ANY of these patterns appear → msh06_source = "practice_id"
Otherwise → msh06_source = "customer_id" (default)
```

**Step 4: Update LLM Prompt**

Added to `markdown_executor.py`:
```python
system_prompt = f"""
CRITICAL PATTERN DETECTION - MSH VALUE:
Before deciding msh06_source, CAREFULLY check if ticket description contains ANY of these phrases:
1. "MSH value is the Practice ID"
2. "MSH value is the practice ID"
...

If ANY phrase found → msh06_source = "practice_id"
If NONE found → msh06_source = "customer_id" (DEFAULT)

This is the MOST IMPORTANT pattern to detect.
"""
```

**Step 5: Add Examples to Memory**

Added to `MEMORY.md`:
```markdown
### EMR Integration - MSH Value Detection (CRITICAL)
- **Default**: msh06_receiving_facility = customer_id
- **Exception**: When ticket EXPLICITLY says "MSH value is the Practice ID"
- **Examples**:
  - VP-15979: No MSH mention → msh06 = 18235 (customer_id) ✅
  - VP-15791: Says "MSH value is the Practice ID" → msh06 = 127265 (practice_id) ✅
```

**Step 6: Test and Verify**

```python
# Test VP-15791 (with pattern)
result = executor._llm_analyze_with_skill(ticket_15791, ...)
# MSH Source: practice_id ✅

# Test VP-15979 (without pattern)
result = executor._llm_analyze_with_skill(ticket_15979, ...)
# MSH Source: customer_id ✅
```

---

## Iteration 4: Automatic Learning from Conversation

### The Problem

After implementing markdown-driven architecture and manual learning via `/pattern`, `/gotcha` commands, we discovered:

```
User: "你錯了，Anna Emanuel 在 3 個不同的 practices"
  ↓
Agent responds correctly
  ↓
❌ Learning NOT automatically saved to .md files
  ↓
User must type /pattern or /gotcha to save
  ↓
Same mistake could happen in next conversation
```

**The Issue:** The agent had learning capability (`MemoryManager.learn_gotcha()`) but it was:
- Manual only (user must invoke)
- Not integrated into conversation flow
- Easy to forget to use

### The Solution: Auto-Learner

Create an `AutoLearner` class that:
1. **Detects corrections** in user messages automatically
2. **Extracts learnings** using LLM
3. **Updates markdown files** immediately
4. **Shows what was learned** to user

#### File Structure

```
src/memory/
├── manager.py          # MemoryManager with learn_gotcha(), learn_qa()
└── auto_learner.py     # NEW: AutoLearner with automatic detection
```

#### AutoLearner Implementation

```python
# src/memory/auto_learner.py

class AutoLearner:
    """Automatically extract learnings from user feedback."""

    async def learn_from_feedback(
        self,
        user_message: str,
        agent_response: str,
        context: str
    ) -> dict:
        """Extract learning and update memory files."""
        # 1. Detect if this is a correction
        is_correction = self._detect_correction(user_message)

        if not is_correction:
            return {"learned": False}

        # 2. Extract structured learning using LLM
        learning = await self._extract_learning(
            user_message, agent_response, context
        )

        # 3. Apply the learning
        result = await self._apply_learning(learning)

        return {
            "learned": True,
            "updated_files": result.get("updated_files", [])
        }

    def _detect_correction(self, user_message: str) -> bool:
        """Detect if user message contains a correction."""
        indicators = [
            "錯了", "錯誤", "不對", "你漏了", "沒注意到",
            "wrong", "incorrect", "mistake", "missing",
            "應該是", "需要", "注意",
        ]
        return any(i in user_message.lower() for i in indicators)

    async def _extract_learning(self, user_message, agent_response, context):
        """Use LLM to extract structured learning."""
        system_prompt = """Extract learning from feedback in JSON:
{
    "category": "pattern" | "gotcha" | "ms-rule",
    "title": "Brief title",
    "problem": "What agent got wrong",
    "solution": "What should be done instead",
    "files_to_update": ["SKILL.md", "MEMORY.md"],
}"""
        # Call LLM to extract learning...
```

#### Integration into Conversation Flow

```python
# src/prompt_interactive.py

class PromptToolkitInteractiveAgent:
    def __init__(self):
        # ... existing initialization ...
        self.auto_learner = get_auto_learner(claude=self.processor.claude)

    def handle_ask(self, question: str):
        # ... get LLM response ...
        answer = response.content[0].text
        console.print(Panel(answer, ...))

        # NEW: Auto-learn from feedback
        learning_result = asyncio.run(self.auto_learner.learn_from_feedback(
            user_input=question,
            agent_response=answer,
            context="General conversation"
        ))

        if learning_result.get("learned"):
            updated = learning_result.get("updated_files", [])
            console.print(Panel(
                f"🧠 Learned: {learning['title']}\n"
                f"Updated: {', '.join(updated)}",
                title="Auto-Learning",
                border_style="yellow"
            ))

        # ... rest of method ...
```

#### Result

Now when user corrects the agent:

```
User: "你漏了 Anna Emanuel (43262) 出現在 3 個不同的 practices"
  ↓
Agent responds
  ↓
🧠 Auto-Learning detected
  ↓
Extracted: {
  "category": "pattern",
  "title": "Multi-Practice Provider Mappings",
  "problem": "Agent assumed providers are unique to practices",
  "solution": "Each (provider, practice) combination needs its own record"
}
  ↓
✅ Updated MEMORY.md automatically
  ↓
Agent shows: "🧠 Learned: Multi-Practice Provider Mappings"
```

### Key Insight

> **The agent should learn DURING conversation, not AFTER.**

Instead of:
- User corrects → Agent responds → User types `/pattern` → Agent saves

Now:
- User corrects → Agent responds → **Agent automatically learns**

---

## Principles of Self-Iteration

### 1. Separation of Concerns

| Layer | Purpose | Format |
|-------|---------|--------|
| **Interface** | Connect to external systems | Code (Python/TS) |
| **Behavior** | What to do, when, how | Markdown |
| **Memory** | Learnings from feedback | Markdown |
| **Execution** | Following the plan | Code (minimal) |

### 2. Progressive Enhancement

```
Start Simple
    ↓
Add Feedback Loops
    ↓
Extract Patterns to Markdown
    ↓
Refactor to Configuration
    ↓
Agent becomes Self-Improving
```

### 3. The "Teach, Don't Code" Principle

**Instead of:**
```python
if "MSH value is the Practice ID" in ticket.description:
    msh06_source = "practice_id"
else:
    msh06_source = "customer_id"
```

**Do this:**
```markdown
## CRITICAL PATTERN DETECTION

Check if ticket says MSH value should be Practice ID. Look for:
- "MSH value is the Practice ID"
- "MSH value is the practice ID"
...
```

The LLM learns the pattern from documentation, not from if-statements.

### 4. Highlight What Matters

When updating prompts:
1. **Put critical info at the TOP**
2. **Use CAPS for emphasis**
3. **Repeat key patterns**
4. **Provide concrete examples**

```python
system_prompt = f"""
CRITICAL PATTERN DETECTION - MSH VALUE:
[Most important section]

If ANY phrase found → msh06_source = "practice_id"
This is the MOST IMPORTANT pattern to detect.
Missing this causes incorrect data!
"""
```

---

## Patterns for Agent Evolution

### Pattern 1: From Functions to Skills

**Before:**
```python
def handle_emr_ticket(ticket):
    # 200 lines of logic
```

**After:**
```markdown
# EMR Integration Skill

## Purpose
Handle EMR Integration tickets...

## Critical Rules
- Rule 1
- Rule 2

## Execution Flow
Step 1, 2, 3...
```

### Pattern 2: From Code to Configuration

**Before:**
```python
tools = {
    "get-customer-rpc": {
        "path": "scripts/get-customer-rpc.ts",
        "params": ["provider-id"]
    }
}
```

**After:**
```markdown
## Tools

### get-customer-rpc
- **Path**: `scripts/get-customer-rpc.ts`
- **Purpose**: Fetch provider data from gRPC
- **Usage**: `--provider-id={id}`
```

### Pattern 3: From Implicit to Explicit

**Before:**
```python
# Agent implicitly uses customer_id for msh06
msh06 = customer_id  # No explanation why
```

**After:**
```markdown
## MSH Value Detection

**DEFAULT**: msh06_receiving_facility = customer_id
**EXCEPTION**: When ticket says "MSH value is the Practice ID"

**Why**: This ensures correct HL7 routing
**How to detect**: [list of phrases]
```

### Pattern 4: The Three-File Architecture

```
SKILL.md          ← How to do this specific task
TOOLS.md          ← What tools are available
MEMORY.md/SOUL.md ← What we've learned
```

---

## Checklist for Creating Self-Iterating Agents

### Phase 1: Initial Design

- [ ] Define agent's purpose and scope
- [ ] Identify key skills/capabilities needed
- [ ] Create `SOUL.md` for core philosophy
- [ ] Create `IDENTITY.md` for agent role
- [ ] Create `TOOLS.md` for available tools

### Phase 2: Skill Structure

- [ ] Create `skills/` directory
- [ ] For each capability, create `skills/{name}/SKILL.md`
- [ ] Each SKILL.md should have:
  - [ ] Metadata (name, type, agent, priority)
  - [ ] Purpose section
  - [ ] Critical Rules section
  - [ ] Execution Flow section
  - [ ] Examples section

### Phase 3: Execution Engine

- [ ] Create `SkillLoader` to read markdown skills
- [ ] Create `MarkdownExecutor` to:
  - [ ] Load skill from markdown
  - [ ] Pass skill content to LLM
  - [ ] Get structured plan from LLM
  - [ ] Execute the plan
- [ ] Separate planning (LLM) from execution (code)

### Phase 4: Feedback Loop

- [ ] After each user correction:
  - [ ] Identify what went wrong
  - [ ] Update relevant SKILL.md
  - [ ] Update MEMORY.md with learning
  - [ ] Update LLM prompts to highlight the pattern
  - [ ] Test with examples
- [ ] Create `MEMORY.md` structure:
  - [ ] Gotchas section
  - [ ] Questions section
  - [ ] Patterns section

### Phase 5: Testing

- [ ] Test with positive examples (should work)
- [ ] Test with negative examples (should fail correctly)
- [ ] Test edge cases
- [ ] Verify default behavior
- [ ] Verify exception handling

### Phase 6: Documentation

- [ ] Document the architecture
- [ ] Document iteration process
- [ ] Create examples of common patterns
- [ ] Document how to add new skills

---

## Common Pitfalls

### Pitfall 1: Too Much in Code

**Symptom:** Frequent code changes for behavior tweaks

**Solution:** Move behavior to markdown

### Pitfall 2: Buried Critical Info

**Symptom:** LLM misses important patterns

**Solution:** Put critical patterns at the TOP of prompts, use CAPS

### Pitfall 3: No Default Behavior

**Symptom:** Agent behaves inconsistently

**Solution:** Always define DEFAULT and EXCEPTIONS explicitly

### Pitfall 4: Scattered Learning

**Symptom:** Same mistake repeated

**Solution:** Centralize learnings in MEMORY.md with concrete examples

### Pitfall 5: No Feedback Loop

**Symptom:** Agent doesn't improve over time

**Solution:** Systematic process: Feedback → Update → Test → Document

---

## Measuring Agent Maturity

| Level | Characteristic |
|-------|----------------|
| **Level 1** | Hardcoded logic, code changes for behavior |
| **Level 2** | Data-driven, structured plans from LLM |
| **Level 3** | Markdown-driven, skills in `.md` files |
| **Level 4** | Self-improving, learns from feedback |
| **Level 5** | Autonomous, adds own skills |

**Our Agent: Level 3 → Level 4**

---

## Quick Reference: Adding New Capabilities

### 1. Create the Skill

```bash
mkdir -p skills/your-skill
touch skills/your-skill/SKILL.md
```

### 2. Document the Skill

```markdown
# Your Skill Name

## Metadata
```yaml
name: your-skill
type: category
agent: your-agent
priority: medium
```

## Purpose
What this skill does...

## Critical Rules
Rules to follow...

## Execution Flow
Step-by-step...

## Examples
Example 1: ...
Example 2: ...
```

### 3. Update TOOLS.md (if new tools needed)

### 4. Update AGENTS.md (if new agent type)

### 5. Test

```python
skill = loader.get_skill("your-skill")
result = executor.execute_with_skill(ticket, skill)
```

---

## Implementing Auto-Learner

> Step-by-step guide to add automatic learning capability to your agent

### Overview

The Auto-Learner enables your agent to **automatically extract learnings from user feedback** during conversation and update markdown files without manual commands.

### File Structure

```
src/memory/
├── manager.py          # MemoryManager with read/write methods
└── auto_learner.py     # AutoLearner with automatic detection
```

### Step 1: Create AutoLearner Class

```python
# src/memory/auto_learner.py

from pathlib import Path
from anthropic import Anthropic
from .manager import MemoryManager, get_memory_manager

class AutoLearner:
    """Automatically extract learnings from user feedback."""

    def __init__(self, claude: Anthropic | None = None, memory_manager: MemoryManager | None = None):
        self.memory = memory_manager or get_memory_manager()
        self.claude = claude
        self.agent_root = self.memory.agent_root

    async def learn_from_feedback(
        self,
        user_message: str,
        agent_response: str,
        context: str
    ) -> dict:
        """Extract learning and update memory files.

        Returns: {"learned": bool, "updated_files": [str]}
        """
        # 1. Detect correction
        if not self._detect_correction(user_message):
            return {"learned": False, "reason": "No correction detected"}

        # 2. Extract learning using LLM
        learning = await self._extract_learning(user_message, agent_response, context)

        if not learning.get("success"):
            return {"learned": False, "error": learning.get("error")}

        # 3. Apply the learning
        result = await self._apply_learning(learning)

        return {
            "learned": True,
            "learning": learning,
            "updated_files": result.get("updated_files", []),
        }

    def _detect_correction(self, user_message: str) -> bool:
        """Detect if user message contains a correction."""
        correction_indicators = [
            # Chinese
            "錯了", "錯誤", "不對", "不是這樣", "你漏了", "沒注意到",
            "應該是", "需要", "注意", "記得", "重要",
            # English
            "wrong", "incorrect", "mistake", "missing", "you should",
            "should be", "need to", "note", "remember", "important",
        ]

        user_lower = user_message.lower()
        return any(indicator in user_lower for indicator in correction_indicators)

    async def _extract_learning(
        self, user_message: str, agent_response: str, context: str
    ) -> dict:
        """Use LLM to extract structured learning from feedback."""

        if not self.claude:
            return {"success": False, "error": "No Claude client available"}

        system_prompt = """You are a learning extraction system.
Extract structured learning from user feedback to an AI agent.

Respond in JSON format:
{
    "success": true,
    "category": "pattern" | "gotcha" | "ms-rule" | "multi-practice",
    "title": "Brief title",
    "problem": "What the agent got wrong",
    "solution": "What should be done instead",
    "files_to_update": ["SKILL.md", "MEMORY.md"],
    "suggested_content": "markdown content to add (optional)"
}"""

        user_prompt = f"""User feedback:
{user_message}

Agent response:
{agent_response[:1000]}

Context:
{context[:500]}

Extract the learning as JSON."""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            import json
            content = response.content[0].text

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_learning(self, learning: dict) -> dict:
        """Apply the learning by updating relevant markdown files."""
        updated_files = []

        category = learning.get("category")
        title = learning.get("title", "Untitled Learning")
        problem = learning.get("problem", "")
        solution = learning.get("solution", "")

        # Update based on category
        if category in ["pattern", "gotcha", "multi-practice"]:
            # Add to MEMORY.md
            self.memory.learn_gotcha(repo=title, gotcha=problem, solution=solution)
            updated_files.append("MEMORY.md")

        if category == "ms-rule":
            # Update SKILL.md with suggested content
            suggested = learning.get("suggested_content", "")
            if suggested:
                self._update_skill_md(title, suggested)
                updated_files.append("SKILL.md")

        return {"updated_files": updated_files}

    def _update_skill_md(self, title: str, content: str):
        """Update SKILL.md with new content."""
        skill_path = self.agent_root / "skills" / "emr-integration" / "SKILL.md"

        if not skill_path.exists():
            return

        current_content = skill_path.read_text(encoding="utf-8")

        # Add before the final "---" line
        if "---" in current_content[-500:]:
            insert_pos = current_content.rfind("---")
            new_content = current_content[:insert_pos] + content + "\n\n---" + current_content[insert_pos + 3:]
            skill_path.write_text(new_content, encoding="utf-8")


# Singleton instance
_auto_learner: AutoLearner | None = None


def get_auto_learner(claude: Anthropic | None = None) -> AutoLearner:
    """Get the singleton AutoLearner instance."""
    global _auto_learner
    if _auto_learner is None:
        _auto_learner = AutoLearner(claude=claude)
    return _auto_learner
```

### Step 2: Fix MemoryManager.learn_gotcha()

Make sure the `learn_gotcha` method correctly inserts entries:

```python
# src/memory/manager.py

def learn_gotcha(self, repo: str, gotcha: str, solution: str):
    """Add a learned gotcha to MEMORY.md."""
    memory = self.read_memory()

    # Find or create Gotchas section
    if "## Gotchas" not in memory:
        memory += "\n\n## Gotchas\n"

    entry = f"\n#### {repo}\n- **Problem**: {gotcha}\n- **Solution**: {solution}\n"

    # Insert after "## Gotchas" header
    if "## Gotchas\n" in memory:
        memory = memory.replace("## Gotchas\n", f"## Gotchas\n{entry}")
    else:
        memory += entry

    self.memory_path.write_text(memory, encoding="utf-8")
```

**Common Bug:** Looking for "### Common Errors" which doesn't exist. Use the fixed version above.

### Step 3: Integrate into Conversation Flow

Add auto-learning after each LLM response:

```python
# src/prompt_interactive.py

from src.memory.auto_learner import get_auto_learner

class PromptToolkitInteractiveAgent:
    def __init__(self):
        # ... existing init ...
        self.auto_learner = get_auto_learner(claude=self.processor.claude)

    def handle_ask(self, question: str):
        # ... get LLM response ...
        answer = response.content[0].text
        console.print(Panel(answer, ...))

        # Auto-learn from user feedback
        import asyncio
        try:
            learning_result = asyncio.run(self.auto_learner.learn_from_feedback(
                user_input=question,
                agent_response=answer,
                context="General conversation"
            ))
            if learning_result.get("learned"):
                updated = learning_result.get("updated_files", [])
                learning = learning_result.get("learning", {})
                console.print(Panel(
                    f"[dim]🧠 Learned: {learning.get('title', 'New pattern')}\n"
                    f"[dim]Updated: {', '.join(updated)}[/dim]",
                    title="[bold yellow]Auto-Learning[/bold yellow]",
                    border_style="yellow"
                ))
        except Exception:
            # Don't interrupt conversation for learning errors
            pass

        # ... continue with conversation history ...
```

### Step 4: Test Auto-Learner

```python
# Test script
import asyncio
from src.memory.auto_learner import get_auto_learner

learner = get_auto_learner()

user_message = "你錯了，同一個 provider 可以在多個 practices"
agent_response = "抱歉，我沒注意到這一點..."
context = "VP-15874"

async def test():
    result = await learner.learn_from_feedback(user_message, agent_response, context)
    print(f"Learned: {result.get('learned')}")
    print(f"Updated: {result.get('updated_files', [])}")

asyncio.run(test())
```

### Output Example

When the agent learns from feedback, it shows:

```
┌─────────────────────────────────────────┐
│ 🧠 Auto-Learning                        │
├─────────────────────────────────────────┤
│ 🧠 Learned: Multi-Practice Provider      │
│   Mappings                               │
│ Updated: MEMORY.md                       │
└─────────────────────────────────────────┘
```

### Category Mappings

| Category | When to Use | Files Updated |
|----------|-------------|----------------|
| `pattern` | General pattern learned | MEMORY.md |
| `gotcha` | Common pitfall/solution | MEMORY.md |
| `ms-rule` | Markdown skill rule | SKILL.md |
| `multi-practice` | Provider in multiple practices | SKILL.md + MEMORY.md |

### Tips

1. **Don't interrupt conversation**: Wrap auto-learning in try/except
2. **Show feedback**: Let user see what was learned
3. **Use singleton**: AutoLearner should be a single instance
4. **Async compatible**: Use `asyncio.run()` for sync codebases

---

## Conclusion

A self-iterating agent is not built in one day. It evolves through:

1. **Recognition** of hard-coded patterns
2. **Extraction** to configuration
3. **Documentation** of behavior
4. **Learning** from feedback
5. **Iteration** on the system

The key insight is that **LLMs are better at following documented patterns than executing hardcoded logic**. By storing behavior in markdown and letting LLMs interpret it, we create agents that can be trained by editing text files rather than writing code.

---

*Document created: 2026-04-07*
*Agent: LIS Code Agent*
*Architecture: Markdown-Driven, Self-Iterating*

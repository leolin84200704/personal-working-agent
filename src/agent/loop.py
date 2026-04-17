"""
Agent Loop - Claude tool_use loop with raw signal feedback.

Architecture:
- No intent classification layer (model decides directly)
- No skill abstraction (model calls tools directly)
- Tools return raw/trimmed data (no Python interpretation)
- Tiered context loading:
    Tier 1: SOUL_CORE + IDENTITY + USER (always, ~5KB)
    Tier 2: Relevant MEMORY/SOUL sections via vector search (~2-5KB)
    Tier 3: memory_search tool (model pulls on demand)
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from anthropic import Anthropic
from rich.console import Console

from src.auth import resolve_api_key
from src.agent.state import ConversationContext, Plan, PlanStep
from src.agent.sub_agent import SubAgentManager
from src.agent.task_manager import TaskManager
from src.agent.background import BackgroundRunner
from src.agent.compaction import CompactionManager
from src.agent.permissions import PermissionManager
from src.memory.short_term import ShortTermMemoryManager
from src.memory.distiller import MemoryDistiller
from src.config import get_settings
from src.memory.manager import MemoryManager
from src.memory.vector_store import VectorStore
from src.memory.indexer import (
    retrieve_relevant_knowledge,
    update_relevance_score,
    index_memory_file,
    index_soul_details,
    KNOWLEDGE_COLLECTION,
)
from src.tools.definitions import ALL_TOOL_DEFINITIONS
from src.tools.executors import execute_tool
from src.utils.logger import get_logger

logger = get_logger()
console = Console()
settings = get_settings()

# Token budget for system prompt (~4 chars per token)
TIER1_BUDGET = 6000   # ~1500 tokens for core rules
TIER2_BUDGET = 8000   # ~2000 tokens for retrieved knowledge
TIER2_RESULTS = 5     # Max knowledge sections to retrieve

# Max tool_use iterations per message to prevent infinite loops
MAX_TOOL_ROUNDS = 25

# Tool categories for plan mode filtering
READ_ONLY_TOOLS = {
    "read_file", "search_files", "grep",
    "git_status", "git_diff", "git_log",
    "jira_get_ticket", "jira_get_assigned", "jira_search",
    "memory_search",
    "web_fetch", "web_search",
}
ALWAYS_AVAILABLE = {
    "task_create", "task_update", "task_get", "task_list",
    "stm_create", "stm_read", "stm_append", "stm_search", "stm_get_failures",
}
PLANNING_ALLOWED = READ_ONLY_TOOLS | ALWAYS_AVAILABLE | {"create_plan", "exit_plan_mode"}
PLANNING_EXCLUDED = {"create_plan", "exit_plan_mode"}

# Meta tools handled directly by the loop (not dispatched to executors)
META_TOOLS = {
    "enter_plan_mode", "create_plan", "exit_plan_mode",
    "spawn_agent", "list_agents",
    "task_create", "task_update", "task_get", "task_list",
    "run_background", "get_background_task", "list_background_tasks",
    "stm_create", "stm_read", "stm_append", "stm_search", "stm_get_failures",
    "stm_distill", "cross_ticket_review", "compress_knowledge",
}


class AgentLoop:
    """
    Claude tool_use loop.

    The model directly controls which tools to call and in what order.
    System prompt provides domain knowledge (SOUL, IDENTITY, USER, MEMORY).
    Tools return raw data. The model does all interpretation.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.context = ConversationContext(session_id=self.session_id)

        self.claude = Anthropic(
            api_key=resolve_api_key(settings.anthropic_api_key),
            base_url=settings.anthropic_base_url,
        )
        self.memory_manager = MemoryManager()

        # Vector store for retrieval
        self._vector_store: VectorStore | None = None
        self._knowledge_indexed = False

        # Managers
        self.sub_agent_manager = SubAgentManager(self.session_id, claude_client=self.claude)
        self.task_manager = TaskManager()
        self.background_runner = BackgroundRunner()
        self.compaction_manager = CompactionManager(claude_client=self.claude)
        self.permission_manager = PermissionManager(
            config_path=settings.agent_root / "permissions.json"
        )
        self.stm_manager = ShortTermMemoryManager(vector_store=self._vector_store)
        self.distiller = MemoryDistiller(claude_client=self.claude)

        # Callback for streaming tool events to WebSocket
        self.on_tool_use: Callable[[str, dict], None] | None = None
        self.on_tool_result: Callable[[str, str], None] | None = None

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = VectorStore(persist_path=str(settings.chroma_path))
        return self._vector_store

    def _ensure_knowledge_indexed(self) -> None:
        """Index MD files into ChromaDB if not already done this session."""
        if self._knowledge_indexed:
            return
        try:
            collection = self.vector_store.client.get_or_create_collection(
                name=KNOWLEDGE_COLLECTION,
            )
            if collection.count() == 0:
                logger.info("Indexing knowledge base for the first time...")
                n1 = index_memory_file(self.vector_store)
                n2 = index_soul_details(self.vector_store)
                logger.info(f"Indexed {n1} MEMORY sections + {n2} SOUL sections")
            self._knowledge_indexed = True
        except Exception as e:
            logger.warning(f"Knowledge indexing failed: {e}")
            self._knowledge_indexed = True  # Don't retry every message

    def _build_system_prompt(self, user_message: str = "") -> str:
        """
        Build the system prompt with tiered context loading.

        Tier 1 (always): SOUL_CORE.md + IDENTITY.md + USER.md (~5KB)
        Tier 2 (retrieved): Relevant MEMORY/SOUL sections based on user_message (~2-5KB)
        Tier 3 (on-demand): memory_search tool — model pulls when it needs more
        """
        # ── Tier 1: Always loaded (core rules, identity, preferences) ──
        soul_core_path = settings.agent_root / "SOUL_CORE.md"
        if soul_core_path.exists():
            soul_core = soul_core_path.read_text(encoding="utf-8")
        else:
            # Fallback: use full SOUL.md if SOUL_CORE.md doesn't exist yet
            soul_core = self.memory_manager.read_soul()

        identity = self.memory_manager.read_identity()
        user = self.memory_manager.read_user()

        # ── Tier 2: Retrieved knowledge relevant to current message ──
        retrieved_context = ""
        if user_message:
            self._ensure_knowledge_indexed()
            try:
                results = retrieve_relevant_knowledge(
                    self.vector_store,
                    query=user_message,
                    n_results=TIER2_RESULTS,
                )
                if results:
                    sections = []
                    total_chars = 0
                    for r in results:
                        section_text = f"### {r['title']}\n{r['text']}"
                        if total_chars + len(section_text) > TIER2_BUDGET:
                            break
                        sections.append(section_text)
                        total_chars += len(section_text)

                    if sections:
                        retrieved_context = "\n\n".join(sections)
            except Exception as e:
                logger.debug(f"Knowledge retrieval failed: {e}")

        # ── Assemble prompt ──
        prompt = f"""You are LIS Code Agent, Leo's AI coding assistant for LIS (Laboratory Information System) projects.

## Instructions
- Always respond in Traditional Chinese (繁體中文) unless explicitly asked for English
- Be concise and direct
- When unsure, ask clarifying questions
- Show your reasoning process when executing complex tasks
- Always verify data before making changes (read before write, query before insert)
- Use tools to gather information — do not guess or assume
- Use the memory_search tool if you need knowledge not shown below

## Core Rules
{soul_core}

## Identity
{identity}

## User Preferences
{user}"""

        if retrieved_context:
            prompt += f"""

## Relevant Knowledge (retrieved for this message)
{retrieved_context}"""

        if self.context.mode == "planning":
            prompt += """

## 規劃模式（目前啟用）
你現在處於規劃模式，只能使用唯讀工具進行調查和分析。
- 先充分了解問題（讀 code、查 ticket、搜尋相關檔案）
- 然後使用 create_plan 建立結構化的執行計畫
- 等使用者確認後，使用 exit_plan_mode 退出規劃模式並開始執行"""
        else:
            prompt += """

## 規劃模式
對於複雜任務（多檔案修改、需求不明確、有風險的操作），
建議先使用 enter_plan_mode 進入規劃模式，調查後制定計畫再執行。
對於簡單的查詢或單一操作，可以直接執行。

## 子 Agent
對於可拆分的子任務，可以使用 spawn_agent 生成子 agent 來獨立處理。
- explore: 唯讀調查（搜檔案、讀 code、看 git history）
- analyze: 分析（含 Jira ticket 和 memory 查詢）
- code: 完整工具集，可修改程式碼
- debate_pro: 正方辯論（為方案辯護）
- debate_con: 反方辯論（質疑方案、找風險）

## Work Loop（完整工作流程）
當使用者要求處理 ticket 時，啟動 Work Loop：
1. Retrieve: stm_search 找類似經驗 + memory_search 找相關知識
2. Analyze: jira_get_ticket + 讀 code + stm_create 開始記錄
3. Debate: spawn_agent debate_pro/debate_con 正反辯論
4. Discuss: 呈現分析和方案，等使用者確認（Man-in-the-loop）
5. Execute: create branch + 改 code + 測試
6. Review: 給使用者看 diff 和結果，等 feedback
7. Complete: commit + push + 總結
8. Retrospective: spawn_agent analyze 反思 + 記錄到 stm_append
9. Memory Update: stm_distill 蒸餾到長期記憶

每一步都用 stm_append 記錄過程。失敗時記到 Failures 區段。"""

        return prompt

    async def process_message(self, message: str) -> dict[str, Any]:
        """
        Process a user message through the Claude tool_use loop.

        Flow:
        1. Build system prompt with domain context
        2. Send message + conversation history to Claude with tools
        3. If Claude returns tool_use → execute tools → send results back
        4. Loop until Claude returns final text response
        5. Return the response

        Args:
            message: User's message

        Returns:
            Dict with response text and metadata
        """
        # Add user message to conversation history
        self.context.add_message("user", message)

        # Compact old messages if conversation is getting long
        self.compaction_manager.compact_if_needed(self.context)

        # Build messages for Claude API
        api_messages = self._build_api_messages()
        system_prompt = self._build_system_prompt(user_message=message)

        tool_calls_made = []

        try:
            for round_num in range(MAX_TOOL_ROUNDS):
                # Call Claude with mode-filtered tools
                available_tools = self._get_available_tools()
                response = self.claude.messages.create(
                    model=settings.default_model,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=available_tools,
                    messages=api_messages,
                )

                # Separate text blocks and tool_use blocks
                text_parts = []
                tool_uses = []

                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                    elif block.type == "tool_use":
                        tool_uses.append(block)

                # If no tool calls, we have the final response
                if not tool_uses:
                    final_text = "\n".join(text_parts)
                    self.context.add_message("assistant", final_text)

                    # Store conversation in vector store for future retrieval
                    self._learn(message)

                    return {
                        "response": final_text,
                        "tool_calls": tool_calls_made,
                        "rounds": round_num + 1,
                    }

                # Add assistant's response (with tool_use blocks) to messages
                api_messages.append({
                    "role": "assistant",
                    "content": [self._block_to_dict(b) for b in response.content],
                })

                # Execute each tool and collect results
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use.name
                    tool_input = tool_use.input

                    # Notify callback (for WebSocket streaming)
                    if self.on_tool_use:
                        self.on_tool_use(tool_name, tool_input)

                    logger.info(f"Tool: {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:200]})")

                    # Execute: meta tools handled here, others go through permission check + executors
                    meta_result = self._execute_meta_tool(tool_name, tool_input)
                    if meta_result is not None:
                        result = meta_result
                    else:
                        allowed, reason = self.permission_manager.check(tool_name, tool_input)
                        if not allowed:
                            result = f"Permission denied: {reason}"
                        else:
                            result = execute_tool(tool_name, tool_input)

                    # Notify callback
                    if self.on_tool_result:
                        self.on_tool_result(tool_name, result[:500])

                    logger.info(f"Result: {result[:200]}...")

                    tool_calls_made.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result_preview": result[:200],
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    })

                # Add tool results as the next user message
                api_messages.append({
                    "role": "user",
                    "content": tool_results,
                })

            # Hit max rounds
            final_text = "\n".join(text_parts) if text_parts else "（已達最大工具呼叫次數限制）"
            self.context.add_message("assistant", final_text)

            return {
                "response": final_text,
                "tool_calls": tool_calls_made,
                "rounds": MAX_TOOL_ROUNDS,
                "warning": "max_tool_rounds_reached",
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                "response": f"抱歉，處理時發生錯誤: {str(e)}",
                "error": str(e),
                "tool_calls": tool_calls_made,
            }

    def _build_api_messages(self) -> list[dict[str, Any]]:
        """
        Build the messages list for the Claude API from conversation history.

        Keeps recent conversation for context, older messages get trimmed.
        """
        messages = []
        recent = self.context.get_recent_messages(settings.max_conversation_history)

        for msg in recent:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        return messages

    def _block_to_dict(self, block) -> dict[str, Any]:
        """Convert an API response block to a dict for re-sending."""
        if block.type == "text":
            return {"type": "text", "text": block.text}
        elif block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        return {"type": block.type}

    def _get_available_tools(self) -> list[dict]:
        """Return tool definitions filtered by current mode."""
        if self.context.mode == "planning":
            return [t for t in ALL_TOOL_DEFINITIONS if t["name"] in PLANNING_ALLOWED]
        return [t for t in ALL_TOOL_DEFINITIONS if t["name"] not in PLANNING_EXCLUDED]

    def _execute_meta_tool(self, name: str, input_data: dict) -> str | None:
        """Handle meta tools that modify agent state. Returns None if not a meta tool."""
        if name == "enter_plan_mode":
            self.context.mode = "planning"
            self.context.current_plan = None
            return "已進入規劃模式。現在只能使用唯讀工具。請先調查問題，然後用 create_plan 建立執行計畫。"

        if name == "create_plan":
            steps = [
                PlanStep(
                    description=s["description"],
                    tool=s.get("tool", ""),
                    reasoning=s.get("reasoning", ""),
                )
                for s in input_data.get("steps", [])
            ]
            self.context.current_plan = Plan(goal=input_data["goal"], steps=steps)
            return self._format_plan(self.context.current_plan)

        if name == "exit_plan_mode":
            self.context.mode = "normal"
            if self.context.current_plan:
                self.context.current_plan.status = "approved"
            return "已退出規劃模式，所有工具現在都可以使用。可以開始執行計畫。"

        if name == "spawn_agent":
            agent_result = self.sub_agent_manager.spawn(
                task=input_data["task"],
                agent_type=input_data.get("agent_type", "explore"),
                context=input_data.get("context", ""),
            )
            return json.dumps(agent_result.to_dict(), ensure_ascii=False, indent=2)

        if name == "list_agents":
            results = self.sub_agent_manager.list_results()
            if not results:
                return "目前沒有子 agent 結果。"
            return json.dumps(results, ensure_ascii=False, indent=2)

        # ── Task tools ──
        if name == "task_create":
            task = self.task_manager.create(
                title=input_data["title"],
                description=input_data.get("description", ""),
            )
            return json.dumps(task.to_dict(), ensure_ascii=False, indent=2)

        if name == "task_update":
            try:
                task = self.task_manager.update(
                    task_id=input_data["task_id"],
                    status=input_data.get("status"),
                    title=input_data.get("title"),
                    description=input_data.get("description"),
                )
                return json.dumps(task.to_dict(), ensure_ascii=False, indent=2)
            except (KeyError, ValueError) as e:
                return f"Error: {e}"

        if name == "task_get":
            try:
                task = self.task_manager.get(input_data["task_id"])
                return json.dumps(task.to_dict(), ensure_ascii=False, indent=2)
            except KeyError as e:
                return f"Error: {e}"

        if name == "task_list":
            tasks = self.task_manager.list(status_filter=input_data.get("status_filter"))
            return json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=2)

        # ── Background tools ──
        if name == "run_background":
            try:
                bg_task = self.background_runner.run(
                    command=input_data["command"],
                    cwd=input_data.get("cwd"),
                    timeout=min(input_data.get("timeout", 600), 600),
                )
                return json.dumps(bg_task.to_dict(), ensure_ascii=False, indent=2)
            except ValueError as e:
                return f"Error: {e}"

        if name == "get_background_task":
            bg_task = self.background_runner.get(input_data["task_id"])
            if bg_task is None:
                return f"Error: Background task '{input_data['task_id']}' not found"
            return json.dumps(bg_task.to_dict(), ensure_ascii=False, indent=2)

        if name == "list_background_tasks":
            bg_tasks = self.background_runner.list()
            return json.dumps([t.to_dict() for t in bg_tasks], ensure_ascii=False, indent=2)

        # ── Short-Term Memory tools ──
        if name == "stm_create":
            path = self.stm_manager.create(input_data["ticket_id"])
            return f"OK: Created short-term memory at {path}"

        if name == "stm_read":
            return self.stm_manager.read(input_data["ticket_id"])

        if name == "stm_append":
            result = self.stm_manager.append_section(
                ticket_id=input_data["ticket_id"],
                section=input_data["section"],
                content=input_data["content"],
            )
            self.stm_manager.index_ticket(input_data["ticket_id"])
            return result

        if name == "stm_search":
            results = self.stm_manager.search(
                query=input_data["query"],
                n_results=input_data.get("n_results", 5),
            )
            if not results:
                return "No matching short-term memories found."
            return json.dumps(results, ensure_ascii=False, indent=2)

        if name == "stm_get_failures":
            return self.stm_manager.get_failures(input_data["ticket_id"])

        # ── Distill tools ──
        if name == "stm_distill":
            return self.distiller.distill_ticket(input_data["ticket_id"])

        if name == "cross_ticket_review":
            return self.distiller.cross_ticket_review(
                last_n=input_data.get("last_n", 5),
            )

        if name == "compress_knowledge":
            return self.distiller.compress_knowledge(
                max_chars=input_data.get("max_chars", 50000),
            )

        return None

    def _format_plan(self, plan: Plan) -> str:
        lines = [f"執行計畫已建立，等待確認。\n\n目標: {plan.goal}\n"]
        for i, step in enumerate(plan.steps, 1):
            lines.append(f"Step {i}: {step.description}")
            if step.tool:
                lines.append(f"  工具: {step.tool}")
            if step.reasoning:
                lines.append(f"  原因: {step.reasoning}")
        lines.append("\n請確認是否執行此計畫。確認後會退出規劃模式並開始執行。")
        return "\n".join(lines)

    def _learn(self, user_message: str) -> None:
        """
        Learn from this interaction:
        1. Store conversation in vector store
        2. Detect corrections and adjust knowledge relevance scores
        """
        if not settings.auto_update_memory:
            return

        # Store conversation
        try:
            self.vector_store.add(
                collection="conversations",
                documents=[user_message],
                metadatas=[{
                    "session_id": self.session_id,
                    "timestamp": datetime.now().isoformat(),
                }],
                ids=[f"{self.session_id}_{len(self.context.messages)}"],
            )
        except Exception as e:
            logger.debug(f"Failed to store conversation: {e}")

        # Detect corrections: if user's message looks like negative feedback,
        # decrease relevance of knowledge that was loaded for the previous turn.
        # If it looks like acceptance, increase relevance.
        self._update_feedback_scores(user_message)

    def _update_feedback_scores(self, user_message: str) -> None:
        """
        Simple next-state signal: analyze user's message to detect corrections.

        Inspired by OpenClaw-RL's PRM concept, but without RL training.
        Instead of updating model weights, we update knowledge relevance scores.
        """
        msg_lower = user_message.lower()

        # Negative signals (user is correcting the agent)
        negative_patterns = [
            "不對", "不是", "錯了", "no,", "no ", "wrong", "incorrect",
            "不要", "別這樣", "重做", "再試", "redo", "try again",
            "那個是錯的", "搞錯了",
        ]

        # Positive signals (user accepts and moves forward)
        positive_patterns = [
            "好", "ok", "對", "correct", "沒錯", "繼續", "下一步",
            "執行", "proceed", "確認", "就這樣",
        ]

        # Only act if we have prior context (at least one prior assistant message)
        if len(self.context.messages) < 3:
            return

        # Get the previous user message (the one the agent responded to)
        prev_messages = self.context.get_recent_messages(4)
        prev_user_msg = None
        for m in prev_messages[:-1]:  # Exclude current message
            if m.role == "user":
                prev_user_msg = m.content
                break

        if not prev_user_msg:
            return

        try:
            is_negative = any(p in msg_lower for p in negative_patterns)
            is_positive = any(p in msg_lower for p in positive_patterns) and not is_negative

            if is_negative:
                updated = update_relevance_score(
                    self.vector_store,
                    query=prev_user_msg,
                    delta=-0.15,
                )
                if updated:
                    logger.info(f"Feedback: negative signal, decreased relevance for {updated} entries")

            elif is_positive:
                updated = update_relevance_score(
                    self.vector_store,
                    query=prev_user_msg,
                    delta=+0.05,
                )
                if updated:
                    logger.debug(f"Feedback: positive signal, increased relevance for {updated} entries")

        except Exception as e:
            logger.debug(f"Feedback scoring failed: {e}")

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

from src.agent.state import ConversationContext
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
from src.tools.definitions import TOOL_DEFINITIONS
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
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
        )
        self.memory_manager = MemoryManager()

        # Vector store for retrieval
        self._vector_store: VectorStore | None = None
        self._knowledge_indexed = False

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

        # Build messages for Claude API
        api_messages = self._build_api_messages()
        system_prompt = self._build_system_prompt(user_message=message)

        tool_calls_made = []

        try:
            for round_num in range(MAX_TOOL_ROUNDS):
                # Call Claude
                response = self.claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOL_DEFINITIONS,
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

                    # Execute the tool
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

"""
Sub-Agent Manager - Spawn and manage child agents for specific tasks.

Each sub-agent is an independent tool_use loop with:
- Its own system prompt (focused on the task)
- A restricted tool set based on agent type
- A lower iteration limit (15 vs main agent's 25)
- No vector store / learning (lightweight)

Results are returned to the parent agent as structured data.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from anthropic import Anthropic

from src.config import get_settings
from src.memory.manager import MemoryManager
from src.tools.definitions import TOOL_DEFINITIONS
from src.tools.executors import execute_tool
from src.utils.logger import get_logger

logger = get_logger()
settings = get_settings()

EXPLORE_TOOLS = {
    "read_file", "search_files", "grep",
    "git_status", "git_diff", "git_log",
}

ANALYZE_TOOLS = EXPLORE_TOOLS | {
    "jira_get_ticket", "jira_get_assigned", "jira_search",
    "memory_search",
}

CODE_TOOLS = ANALYZE_TOOLS | {
    "edit_file", "write_file", "run_bash",
    "git_create_branch", "git_commit",
}

DEBATE_TOOLS = ANALYZE_TOOLS

AGENT_TYPE_TOOLS = {
    "explore": EXPLORE_TOOLS,
    "analyze": ANALYZE_TOOLS,
    "code": CODE_TOOLS,
    "debate_pro": DEBATE_TOOLS,
    "debate_con": DEBATE_TOOLS,
}

MAX_SUB_AGENT_ROUNDS = 15

TYPE_DESCRIPTIONS = {
    "explore": "你是探索型子 agent。任務是調查和收集資訊，然後回報發現。你只能讀取，不能修改檔案。",
    "analyze": "你是分析型子 agent。任務是分析程式碼、Jira ticket 和相關資訊，提供分析結果。你只能讀取，不能修改檔案。",
    "code": "你是程式碼型子 agent。任務是執行具體的程式碼修改。謹慎操作，確保每次修改都正確。",
    "debate_pro": "你是辯論型子 agent（正方）。你的任務是為提議的方案找出支持的論點和優勢。要客觀但積極地論證方案的可行性。列出具體的技術理由和實務好處。",
    "debate_con": "你是辯論型子 agent（反方）。你的任務是為提議的方案找出風險、弱點和替代方案。要建設性地批評，指出潛在問題並提出改善建議。",
}


class SubAgentResult:
    """Result from a completed sub-agent run."""

    def __init__(self, agent_id: str, agent_type: str, task: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.task = task
        self.response: str = ""
        self.tool_calls: list[dict] = []
        self.rounds: int = 0
        self.status: str = "pending"
        self.created_at: datetime = datetime.now()
        self.completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "task": self.task,
            "response": self.response,
            "tool_calls_count": len(self.tool_calls),
            "rounds": self.rounds,
            "status": self.status,
        }


class SubAgentManager:
    """Manages spawning and tracking of sub-agents."""

    def __init__(self, parent_session_id: str, claude_client: Anthropic):
        self.parent_session_id = parent_session_id
        self.claude = claude_client
        self.results: dict[str, SubAgentResult] = {}
        self._counter = 0

    def spawn(
        self,
        task: str,
        agent_type: str = "explore",
        context: str = "",
    ) -> SubAgentResult:
        self._counter += 1
        agent_id = f"sub_{self.parent_session_id}_{self._counter}"

        result = SubAgentResult(agent_id=agent_id, agent_type=agent_type, task=task)
        self.results[agent_id] = result
        result.status = "running"

        logger.info(f"Spawning sub-agent {agent_id} (type={agent_type}): {task[:100]}")

        try:
            allowed_tool_names = AGENT_TYPE_TOOLS.get(agent_type, EXPLORE_TOOLS)
            tools = [t for t in TOOL_DEFINITIONS if t["name"] in allowed_tool_names]

            system_prompt = self._build_prompt(task, agent_type, context)
            response_data = self._run_loop(system_prompt, task, tools)

            result.response = response_data["response"]
            result.tool_calls = response_data.get("tool_calls", [])
            result.rounds = response_data.get("rounds", 0)
            result.status = "completed"
            result.completed_at = datetime.now()

            logger.info(f"Sub-agent {agent_id} completed in {result.rounds} rounds")

        except Exception as e:
            logger.error(f"Sub-agent {agent_id} failed: {e}", exc_info=True)
            result.response = f"Sub-agent error: {e}"
            result.status = "failed"
            result.completed_at = datetime.now()

        return result

    def _build_prompt(self, task: str, agent_type: str, context: str) -> str:
        memory_manager = MemoryManager()
        identity = memory_manager.read_identity()

        prompt = f"""你是 LIS Code Agent 的子 agent（{agent_type} 類型）。

## 角色
{TYPE_DESCRIPTIONS.get(agent_type, TYPE_DESCRIPTIONS["explore"])}

## 任務
{task}

## 專案資訊
{identity}

## 規則
- 使用繁體中文回覆
- 簡潔直接，專注於任務
- 完成後總結發現和結論
- 不要做任務範圍外的事"""

        if context:
            prompt += f"\n\n## 額外背景\n{context}"

        return prompt

    def _run_loop(
        self,
        system_prompt: str,
        task: str,
        tools: list[dict],
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        tool_calls_made: list[dict] = []
        text_parts: list[str] = []

        for round_num in range(MAX_SUB_AGENT_ROUNDS):
            response = self.claude.messages.create(
                model=settings.default_model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            text_parts = []
            tool_uses = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if not tool_uses:
                return {
                    "response": "\n".join(text_parts),
                    "tool_calls": tool_calls_made,
                    "rounds": round_num + 1,
                }

            messages.append({
                "role": "assistant",
                "content": [
                    {"type": "text", "text": b.text} if b.type == "text"
                    else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                    for b in response.content
                ],
            })

            tool_results = []
            for tool_use in tool_uses:
                logger.info(f"  Sub-agent tool: {tool_use.name}")
                tool_result = execute_tool(tool_use.name, tool_use.input)

                tool_calls_made.append({
                    "tool": tool_use.name,
                    "input": tool_use.input,
                    "result_preview": tool_result[:200],
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_result,
                })

            messages.append({"role": "user", "content": tool_results})

        final = "\n".join(text_parts) if text_parts else "(sub-agent reached max iterations)"
        return {
            "response": final,
            "tool_calls": tool_calls_made,
            "rounds": MAX_SUB_AGENT_ROUNDS,
        }

    def list_results(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.results.values()]

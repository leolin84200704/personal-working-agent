"""
Auto Learner - Automatically extract learnings from user feedback.

This module enables the agent to learn from corrections and update
markdown files automatically during conversation.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from anthropic import Anthropic

from .manager import MemoryManager, get_memory_manager


class AutoLearner:
    """
    Automatically extract learnings from user feedback and update memory.

    When the user corrects the agent, extract:
    1. What the agent got wrong
    2. What the correct behavior should be
    3. Which markdown file to update
    4. What content to add
    """

    def __init__(self, claude: Anthropic | None = None, memory_manager: MemoryManager | None = None):
        self.memory = memory_manager or get_memory_manager()
        self.claude = claude
        self.agent_root = self.memory.agent_root

    async def learn_from_feedback(
        self,
        user_message: str,
        agent_response: str,
        context: str
    ) -> dict[str, Any]:
        """
        Extract learnings from user feedback and update memory files.

        Args:
            user_message: The user's message (may contain corrections)
            agent_response: What the agent responded
            context: Additional context (ticket info, etc.)

        Returns:
            Dict with learning results and what was updated
        """
        # Check if this is a correction
        is_correction = self._detect_correction(user_message)

        if not is_correction:
            return {"learned": False, "reason": "No correction detected"}

        # Extract learning using LLM
        learning = await self._extract_learning(user_message, agent_response, context)

        if not learning.get("success"):
            return {"learned": False, "reason": "Failed to extract learning"}

        # Apply the learning
        result = await self._apply_learning(learning)

        return {
            "learned": True,
            "learning": learning,
            "updated_files": result.get("updated_files", []),
        }

    def _detect_correction(self, user_message: str) -> bool:
        """Detect if user message contains a correction."""
        correction_indicators = [
            "錯了", "錯誤", "不對", "不是這樣", "你漏了", "沒注意到",
            "wrong", "incorrect", "mistake", "missing", "you should",
            "應該是", "需要", "注意", "記得", "重要",
        ]

        user_lower = user_message.lower()
        return any(indicator in user_lower for indicator in correction_indicators)

    async def _extract_learning(
        self,
        user_message: str,
        agent_response: str,
        context: str
    ) -> dict[str, Any]:
        """Use LLM to extract structured learning from feedback."""

        if not self.claude:
            return {"success": False, "error": "No Claude client available"}

        system_prompt = """You are a learning extraction system. Your job is to extract structured learnings from user feedback to an AI agent.

Analyze the user's message and extract:
1. What the agent got wrong
2. What the correct behavior should be
3. Which category this belongs to (pattern/gotcha/ms-rule)
4. Suggested markdown content to add

Respond in JSON format:
{
    "success": true,
    "category": "pattern" | "gotcha" | "ms-rule" | "multi-practice",
    "title": "Brief title",
    "problem": "What the agent got wrong",
    "solution": "What should be done instead",
    "files_to_update": ["SKILL.md", "MEMORY.md"],
    "suggested_content": "markdown content to add"
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

            learning = json.loads(content)
            return learning

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_learning(self, learning: dict[str, Any]) -> dict[str, Any]:
        """Apply the learning by updating relevant markdown files."""
        updated_files = []

        category = learning.get("category")
        title = learning.get("title", "Untitled Learning")
        problem = learning.get("problem", "")
        solution = learning.get("solution", "")
        files_to_update = learning.get("files_to_update", [])

        # Update based on category
        if category in ["pattern", "gotcha"]:
            # Add to MEMORY.md
            self.memory.learn_gotcha(
                repo=title,
                gotcha=problem,
                solution=solution
            )
            updated_files.append("MEMORY.md")

        if category == "ms-rule":
            # Update SKILL.md
            suggested = learning.get("suggested_content", "")
            if suggested:
                self._update_skill_md(title, suggested)
                updated_files.append("SKILL.md")

        if category == "multi-practice":
            # Special handling for multi-practice provider pattern
            self._update_multi_practice_pattern(problem, solution)
            updated_files.append("SKILL.md")
            updated_files.append("MEMORY.md")

        return {"updated_files": updated_files}

    def _update_skill_md(self, title: str, content: str):
        """Update SKILL.md with new content."""
        skill_path = self.agent_root / "skills" / "emr-integration" / "SKILL.md"

        if not skill_path.exists():
            return

        current_content = skill_path.read_text(encoding="utf-8")

        # Add before the final "Last Updated" line
        if "---" in current_content[-500:]:
            insert_pos = current_content.rfind("---")
            new_content = current_content[:insert_pos] + content + "\n\n---" + current_content[insert_pos + 3:]
            skill_path.write_text(new_content, encoding="utf-8")

    def _update_multi_practice_pattern(self, problem: str, solution: str):
        """Update MEMORY.md and SKILL.md for multi-practice provider pattern."""
        # Add to MEMORY.md
        self.memory.learn_gotcha(
            repo="EMR Integration - Multi-Practice Provider",
            gotcha=problem,
            solution=solution
        )

        # Add to SKILL.md
        skill_path = self.agent_root / "skills" / "emr-integration" / "SKILL.md"
        if skill_path.exists():
            current = skill_path.read_text(encoding="utf-8")
            section = f"""

## Multi-Practice Provider Pattern (CRITICAL)

### When Same Provider Appears in Multiple Practices

**Pattern to detect:**
- Ticket contains a table with Practice IDs and Provider IDs
- Same Provider ID appears under multiple Practice IDs
- Example: Same provider name with multiple practice locations

**What it means:**
- Each (Provider, Practice) combination needs its OWN `ehr_integrations` record
- Same provider will have MULTIPLE records with different `clinic_id` values
- Example: Provider 43262 in practices 2930, 8003, 36290 = 3 separate records

**How to handle:**
1. Parse ALL provider-practice mappings from ticket
2. Create ehr_integrations record for EACH combination
3. msh06_receiving_facility = Practice ID for each
4. order_clients.clinic_id = Practice ID for each

---

"""

            # Add before Last Updated
            if "---" in current[-500:]:
                insert_pos = current.rfind("---")
                new_content = current[:insert_pos] + section + "---" + current[insert_pos + 3:]
                skill_path.write_text(new_content, encoding="utf-8")


# Singleton instance
_auto_learner: AutoLearner | None = None


def get_auto_learner(claude: Anthropic | None = None) -> AutoLearner:
    """Get the singleton AutoLearner instance."""
    global _auto_learner
    if _auto_learner is None:
        _auto_learner = AutoLearner(claude=claude)
    return _auto_learner

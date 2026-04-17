"""
Auto Memory Update - Automatically update SOUL/IDENTITY/USER/MEMORY.md
based on conversations and feedback.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.config import get_settings
from src.memory.manager import MemoryManager


class MemoryAutoUpdater:
    """
    Automatically update memory files based on conversations.

    Uses Claude to extract learning from conversations and
    update the appropriate memory files.
    """

    def __init__(self, claude: Anthropic):
        """Initialize the auto updater."""
        self.claude = claude
        self.settings = get_settings()
        self.memory = MemoryManager()

    async def extract_updates(
        self,
        conversation: list[dict[str, str]],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Extract memory updates from a conversation.

        Args:
            conversation: List of messages with "role" and "content"

        Returns:
            Dict with file_type as key and list of updates as value
            {
                "soul": [...],
                "identity": [...],
                "user": [...],
                "memory": [...],
            }
        """
        # Build conversation text
        conv_text = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in conversation
        ])

        # Build system prompt
        system_prompt = """You are analyzing a conversation between a user (Leo) and his AI agent (LIS Code Agent).

Your task is to extract information that should be added to the agent's memory files.

## Memory Files:

### SOUL.md
- Core philosophy and behavioral guidelines
- Branch naming conventions
- Git safety rules
- Decision framework
Only extract updates for SOUL.md if the conversation discusses agent behavior or rules.

### IDENTITY.md
- Agent's role and capabilities
- Repository information
- What the agent does/doesn't do
Only extract updates for IDENTITY.md if new repos are mentioned or capabilities change.

### USER.md
- Leo's preferences and habits
- Communication style
- Work patterns
Only extract updates for USER.md if preferences or work patterns are discussed.

### MEMORY.md
- Q&A pairs
- Patterns and gotchas
- Repository-specific knowledge
Extract factual information that would be useful for future conversations.

## Output Format:

Respond in JSON format:
{
    "soul": [{"section": "section_name", "content": "content to add"}],
    "identity": [{"section": "section_name", "content": "content to add"}],
    "user": [{"section": "section_name", "content": "content to add"}],
    "memory": [{"category": "pattern|gotcha|qa", "content": "content to add"}]
}

If no updates are needed for a file, return an empty array.

Be conservative - only extract clear, factual information. Do not extract opinions unless they are explicitly stated preferences."""

        try:
            response = self.claude.messages.create(
                model=self.settings.default_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": conv_text}],
                system=system_prompt,
                temperature=0.0,
            )

            content = response.content[0].text

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            updates = json.loads(content)

            # Validate structure
            validated = {
                "soul": updates.get("soul", []),
                "identity": updates.get("identity", []),
                "user": updates.get("user", []),
                "memory": updates.get("memory", []),
            }

            return validated

        except Exception as e:
            print(f"Failed to extract memory updates: {e}")
            return {"soul": [], "identity": [], "user": [], "memory": []}

    async def apply_updates(self, updates: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        """
        Apply extracted updates to memory files.

        Args:
            updates: Dict from extract_updates()

        Returns:
            Dict with file_type as key and number of updates applied as value
        """
        applied = {"soul": 0, "identity": 0, "user": 0, "memory": 0}

        # Process each file type
        for file_type, items in updates.items():
            if not items:
                continue

            for item in items:
                try:
                    if file_type == "soul":
                        self._update_soul(item.get("section", ""), item.get("content", ""))
                        applied["soul"] += 1
                    elif file_type == "identity":
                        self._update_identity(item.get("section", ""), item.get("content", ""))
                        applied["identity"] += 1
                    elif file_type == "user":
                        self._update_user(item.get("section", ""), item.get("content", ""))
                        applied["user"] += 1
                    elif file_type == "memory":
                        self._update_memory(item.get("category", "qa"), item.get("content", ""))
                        applied["memory"] += 1
                except Exception as e:
                    print(f"Failed to apply update to {file_type}: {e}")

        return applied

    def _update_soul(self, section: str, content: str) -> None:
        """Update SOUL.md."""
        path = self.settings.soul_path
        current = path.read_text(encoding="utf-8") if path.exists() else ""

        # Check if content already exists
        if content in current:
            return

        # Append with section header
        with open(path, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            f.write(f"\n\n## {section} (Learned {timestamp})\n\n{content}\n")

    def _update_identity(self, section: str, content: str) -> None:
        """Update IDENTITY.md."""
        path = self.settings.identity_path
        current = path.read_text(encoding="utf-8") if path.exists() else ""

        if content in current:
            return

        with open(path, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            f.write(f"\n\n## {section} (Learned {timestamp})\n\n{content}\n")

    def _update_user(self, section: str, content: str) -> None:
        """Update USER.md."""
        path = self.settings.user_path
        current = path.read_text(encoding="utf-8") if path.exists() else ""

        if content in current:
            return

        with open(path, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            f.write(f"\n\n## {section} (Learned {timestamp})\n\n{content}\n")

    def _update_memory(self, category: str, content: str) -> None:
        """Update MEMORY.md."""
        path = self.settings.memory_path
        current = path.read_text(encoding="utf-8") if path.exists() else ""

        if content in current:
            return

        # Use existing memory manager methods
        if category == "qa":
            # Extract question and answer
            if "?" in content:
                parts = content.split("?", 1)
                question = parts[0] + "?"
                answer = parts[1].strip() if len(parts) > 1 else ""
                self.memory.learn_qa(question, answer)
            else:
                self.memory.learn_qa(content, "")
        elif category == "pattern":
            # Try to extract repo and pattern
            self.memory.learn_repo_pattern("general", category, content)
        elif category == "gotcha":
            self.memory.learn_gotcha("general", content, "See description")
        else:
            # General Q&A fallback
            self.memory.learn_qa(f"{category}: {content[:50]}...", content)

    async def process_conversation(
        self,
        conversation: list[dict[str, str]],
        auto_apply: bool = True,
    ) -> dict[str, Any]:
        """
        Process a conversation and optionally apply updates.

        Args:
            conversation: List of messages
            auto_apply: Whether to automatically apply updates

        Returns:
            Dict with extracted and applied updates
        """
        updates = await self.extract_updates(conversation)

        result = {
            "extracted": updates,
            "applied": {},
        }

        if auto_apply:
            applied = await self.apply_updates(updates)
            result["applied"] = applied

        return result

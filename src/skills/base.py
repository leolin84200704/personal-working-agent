"""
Base Skill class - All agent skills inherit from this.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from anthropic import Anthropic

from src.memory.manager import MemoryManager


class Skill(ABC):
    """
    Base class for all agent skills.

    A skill is a specific capability the agent has,
    such as interacting with Jira, editing code, etc.
    """

    def __init__(
        self,
        claude: Anthropic,
        memory: MemoryManager,
    ):
        """Initialize the skill."""
        self.claude = claude
        self.memory = memory

    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """
        Execute the skill.

        Returns:
            Dict with:
                - status: "success" | "error" | "partial"
                - response: str (human-readable description)
                - data: dict (structured result)
                - error: str | None (if status is error)
        """
        pass

    @property
    def name(self) -> str:
        """Get the skill name."""
        return self.__class__.__name__.replace("Skill", "").lower()

    @property
    def description(self) -> str:
        """Get the skill description."""
        return self.__doc__ or "No description available"

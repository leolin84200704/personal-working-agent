"""
Memory Skill - Manage agent memory and learning.
"""
from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from src.skills.base import Skill
from src.memory.manager import MemoryManager
from src.memory.vector_store import VectorStore


class MemorySkill(Skill):
    """Skill for managing agent memory."""

    def __init__(
        self,
        claude: Anthropic,
        memory: MemoryManager,
        vector_store: VectorStore,
    ):
        super().__init__(claude, memory)
        self.vector_store = vector_store

    async def show_memory(self, file_type: str = "all") -> dict[str, Any]:
        """Show memory content."""
        try:
            if file_type == "all" or file_type == "soul":
                soul = self.memory.read_soul()
            else:
                soul = None

            if file_type == "all" or file_type == "identity":
                identity = self.memory.read_identity()
            else:
                identity = None

            if file_type == "all" or file_type == "user":
                user = self.memory.read_user()
            else:
                user = None

            if file_type == "all" or file_type == "memory":
                memory = self.memory.read_memory()
            else:
                memory = None

            # Build response
            parts = []
            if soul:
                parts.append(f"## SOUL\n{soul[:500]}...")
            if identity:
                parts.append(f"## IDENTITY\n{identity[:500]}...")
            if user:
                parts.append(f"## USER\n{user[:500]}...")
            if memory:
                parts.append(f"## MEMORY\n{memory[:500]}...")

            return {
                "status": "success",
                "response": "\n\n".join(parts),
                "data": {
                    "soul": soul if soul else None,
                    "identity": identity if identity else None,
                    "user": user if user else None,
                    "memory": memory if memory else None,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to read memory: {str(e)}",
                "error": str(e),
            }

    async def search_memory(self, query: str, n_results: int = 5) -> dict[str, Any]:
        """Search memory using vector similarity."""
        try:
            results = self.vector_store.search(
                query=query,
                collection="conversations",
                n_results=n_results,
            )

            formatted = [
                f"• {r.get('document', '')[:100]}..."
                for r in results
            ]

            return {
                "status": "success",
                "response": f"Found {len(results)} relevant memories:\n\n" + "\n".join(formatted),
                "data": {"results": results},
            }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Search failed: {str(e)}",
                "error": str(e),
            }

    async def learn(self, content: str, category: str = "general") -> dict[str, Any]:
        """Learn something new and store in memory."""
        try:
            # Add to vector store
            self.vector_store.add(
                collection="conversations",
                documents=[content],
                metadatas=[{"category": category, "timestamp": "now"}],
                ids=[f"manual_{len(content)}"],
            )

            # Also append to MEMORY.md
            self.memory.learn_qa(f"Manual learning ({category})", content)

            return {
                "status": "success",
                "response": f"Learned: {content[:50]}...",
                "data": {"category": category},
            }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to learn: {str(e)}",
                "error": str(e),
            }

    async def execute(self, action: str = "show", **kwargs) -> dict[str, Any]:
        """Execute a memory action."""
        if action == "show":
            return await self.show_memory(kwargs.get("file_type", "all"))
        elif action == "search":
            return await self.search_memory(kwargs.get("query", ""))
        elif action == "learn":
            return await self.learn(
                kwargs.get("content", ""),
                kwargs.get("category", "general"),
            )
        else:
            return {
                "status": "error",
                "response": f"Unknown action: {action}",
            }

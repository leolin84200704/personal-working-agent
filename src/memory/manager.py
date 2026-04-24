"""
Memory Manager - Handles reading and writing memory files.

The memory system is the core learning mechanism for the agent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from src.memory.security_scanner import get_scanner


class MemoryManager:
    """Manages SOUL, IDENTITY, USER, and MEMORY files."""

    def __init__(self, agent_root: Path | None = None):
        if agent_root is None:
            agent_root = Path(__file__).parent.parent.parent
        self.agent_root = Path(agent_root)
        self.memory_dir = self.agent_root

    @property
    def soul_path(self) -> Path:
        return self.agent_root / "SOUL.md"

    @property
    def identity_path(self) -> Path:
        return self.agent_root / "IDENTITY.md"

    @property
    def user_path(self) -> Path:
        return self.agent_root / "USER.md"

    @property
    def memory_path(self) -> Path:
        return self.agent_root / "MEMORY.md"

    def read_soul(self) -> str:
        """Read SOUL.md - agent's core philosophy."""
        return self._read_file(self.soul_path)

    def read_identity(self) -> str:
        """Read IDENTITY.md - agent's role and capabilities."""
        return self._read_file(self.identity_path)

    def read_user(self) -> str:
        """Read USER.md - Leo's preferences."""
        return self._read_file(self.user_path)

    def read_memory(self) -> str:
        """Read MEMORY.md - accumulated knowledge."""
        return self._read_file(self.memory_path)

    def _read_file(self, path: Path) -> str:
        """Read a file, return empty string if not found."""
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def get_branch_prefixes(self) -> dict[str, str]:
        """Get allowed branch prefixes from SOUL.md."""
        soul = self.read_soul()
        prefixes = {}

        # Look for branch naming conventions
        for line in soul.split("\n"):
            if "feature/leo/" in line.lower():
                prefixes["feature"] = "feature/leo"
            elif "bugfix/leo/" in line.lower():
                prefixes["bugfix"] = "bugfix/leo"

        if not prefixes:
            # Default from conversation
            return {"feature": "feature/leo", "bugfix": "bugfix/leo"}

        return prefixes

    def get_allowed_operations(self) -> dict[str, list[str]]:
        """Get allowed git operations from SOUL.md."""
        soul = self.read_soul()
        allowed = []
        blocked = []

        section = None
        for line in soul.split("\n"):
            line = line.strip()
            if "ALLOWED" in line or "允許" in line:
                section = "allowed"
            elif "BLOCKED" in line or "禁止" in line:
                section = "blocked"
            elif section and line.startswith("-") or line.startswith("✅"):
                cmd = self._extract_git_command(line)
                if cmd and section == "allowed":
                    allowed.append(cmd)
                elif cmd and section == "blocked":
                    blocked.append(cmd)
            elif line.startswith("```") or line.startswith("---"):
                section = None

        return {"allowed": allowed, "blocked": blocked}

    def _extract_git_command(self, line: str) -> str | None:
        """Extract git command from a markdown list item."""
        # Remove markdown bullets and emojis
        clean = re.sub(r"^[\-\*\+]\s*", "", line)
        clean = re.sub(r"^[✅❌]\s*", "", clean)
        clean = clean.strip("`").strip()

        if clean.startswith("git "):
            return clean
        return None

    def get_repo_info(self) -> dict[str, dict[str, str]]:
        """Parse repo information from IDENTITY.md."""
        identity = self.read_identity()
        repos = {}

        lines = identity.split("\n")
        current_repo = None

        for line in lines:
            line = line.strip()
            # Match markdown table row: | Name | Purpose | Tech | Status |
            if line.startswith("|") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4 and parts[0] and not parts[0].startswith("Repo"):
                    current_repo = {
                        "purpose": parts[1] if len(parts) > 1 else "",
                        "tech": parts[2] if len(parts) > 2 else "",
                        "status": parts[3] if len(parts) > 3 else "unknown",
                    }
                    repos[parts[0]] = current_repo

        return repos

    def get_user_preferences(self) -> dict[str, Any]:
        """Parse user preferences from USER.md."""
        user = self.read_user()
        prefs = {
            "branch_prefixes": {"feature": "feature/leo", "bugfix": "bugfix/leo"},
            "commit_style": "concise",
            "no_emoji": True,
        }

        # Parse branch prefixes
        for line in user.split("\n"):
            if "feature/leo/" in line:
                prefs["branch_prefixes"]["feature"] = "feature/leo"
            elif "bugfix/leo/" in line:
                prefs["branch_prefixes"]["bugfix"] = "bugfix/leo"

        return prefs

    def learn_repo_pattern(self, repo: str, pattern: str, description: str):
        """Add a learned pattern to MEMORY.md."""
        # Security guard BEFORE any mutation.
        get_scanner().scan(
            f"{repo}\n{pattern}\n{description}",
            context=f"manager:learn_repo_pattern:{repo}",
        )

        memory = self.read_memory()

        # Find or create Patterns section
        if "## Patterns" not in memory:
            memory += "\n\n## Patterns\n\n### Learned Patterns\n"

        # Add the pattern
        new_entry = f"\n### {repo}\n- **{pattern}**: {description}\n"

        # Check if already exists
        if f"### {repo}" in memory:
            # Append to existing repo section
            memory = memory.replace(
                f"### {repo}\n",
                f"### {repo}\n{new_entry}",
            )
        else:
            memory += new_entry

        self.memory_path.write_text(memory, encoding="utf-8")

    def learn_gotcha(self, repo: str, gotcha: str, solution: str):
        """Add a learned gotcha to MEMORY.md."""
        get_scanner().scan(
            f"{repo}\n{gotcha}\n{solution}",
            context=f"manager:learn_gotcha:{repo}",
        )

        memory = self.read_memory()

        # Find or create Gotchas section
        if "## Gotchas" not in memory:
            memory += "\n\n## Gotchas\n"

        entry = f"\n#### {repo}\n- **Problem**: {gotcha}\n- **Solution**: {solution}\n"

        # Insert after "## Gotchas" header
        if "## Gotchas\n" in memory:
            memory = memory.replace("## Gotchas\n", f"## Gotchas\n{entry}")
        else:
            # Append to end
            memory += entry

        self.memory_path.write_text(memory, encoding="utf-8")

    def learn_qa(self, question: str, answer: str):
        """Add a Q&A to MEMORY.md."""
        get_scanner().scan(
            f"{question}\n{answer}",
            context="manager:learn_qa",
        )

        memory = self.read_memory()

        # Find or create Questions section
        if "## Questions" not in memory:
            memory += "\n\n## Questions\n"

        entry = f"\n### Q: {question}\n> **A**: {answer}\n"

        # Insert after Questions header
        memory = memory.replace("## Questions\n", f"## Questions\n{entry}")

        self.memory_path.write_text(memory, encoding="utf-8")

        # Also try to extract patterns from feedback and update Gotchas
        self._extract_and_learn_patterns(question, answer)

    def update_repo_knowledge(self, repo: str, key: str, value: str):
        """Update knowledge about a specific repo in MEMORY.md."""
        get_scanner().scan(
            f"{repo}\n{key}\n{value}",
            context=f"manager:update_repo_knowledge:{repo}",
        )

        memory = self.read_memory()

        section_header = f"### {repo}"
        new_line = f"- **{key}**: {value}"

        if section_header in memory:
            # Add to existing section
            lines = memory.split("\n")
            new_lines = []
            inserted = False

            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.startswith(section_header) and not inserted:
                    # Find end of section (next ### or ##)
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith("###"):
                            new_lines.append(new_line)
                            inserted = True
                            break
                        elif lines[j].startswith("##"):
                            new_lines.append(new_line)
                            inserted = True
                            break
                    if not inserted:
                        new_lines.append(new_line)
                        inserted = True

            memory = "\n".join(new_lines)
        else:
            # Create new section
            if "## Repos" in memory:
                memory += f"\n{section_header}\n{new_line}\n"
            else:
                memory += f"\n## Repos\n\n{section_header}\n{new_line}\n"

        self.memory_path.write_text(memory, encoding="utf-8")

    def get_context_for_ticket(self, ticket_id: str, description: str) -> str:
        """Gather relevant context for processing a ticket."""
        context = ["# Context for Ticket Processing\n"]

        # Add IDENTITY
        context.append("## IDENTITY\n")
        context.append(self.read_identity())

        # Add relevant USER preferences
        context.append("\n## USER Preferences\n")
        prefs = self.get_user_preferences()
        context.append(f"- Branch prefixes: {prefs['branch_prefixes']}")
        context.append(f"- Commit style: {prefs['commit_style']}")
        context.append(f"- No emoji: {prefs['no_emoji']}")

        # Add MEMORY (focused on repos and patterns)
        context.append("\n## MEMORY\n")
        memory = self.read_memory()

        # Extract relevant sections
        relevant_sections = ["## Repos", "## Patterns", "## Gotchas"]
        for section in relevant_sections:
            if section in memory:
                idx = memory.index(section)
                # Find end of section
                end_idx = len(memory)
                for next_section in relevant_sections:
                    if next_section != section and next_section in memory[idx + len(section):]:
                        next_idx = memory.index(next_section, idx + len(section))
                        end_idx = min(end_idx, next_idx)
                context.append(memory[idx:end_idx])

        return "\n".join(context)

    def _extract_and_learn_patterns(self, question: str, answer: str):
        """Extract patterns from feedback and add to Gotchas."""
        combined = f"{question} {answer}".lower()

        # Pattern 1: EMR integration tickets should use lis-emr-backend-v2
        if "emr" in combined and "integration" in combined and "lis-emr-backend-v2" in combined:
            self._add_to_gotchas(
                repo="EMR Tickets",
                problem="EMR integration/order/result tickets often get assigned to wrong repos",
                solution="EMR integration/order/result tickets should primarily use: **lis-emr-backend-v2** (NestJS v2). EMR-Backend (Java) is the legacy system being migrated from."
            )

        # Pattern 2: Migration context
        if "migrate" in combined or "migration" in combined:
            if "emr-backend" in combined and "lis-backend-emr-v2" in combined:
                self._add_to_gotchas(
                    repo="Migration Context",
                    problem="Confusion between old and new EMR systems",
                    solution="**Migration in progress**: EMR-Backend (Java, legacy) → lis-backend-emr-v2 (NestJS, current). Always prefer lis-backend-emr-v2 for new work."
                )

    def _add_to_gotchas(self, repo: str, problem: str, solution: str):
        """Add an entry to the Gotchas section, avoiding duplicates."""
        get_scanner().scan(
            f"{repo}\n{problem}\n{solution}",
            context=f"manager:_add_to_gotchas:{repo}",
        )

        memory = self.read_memory()

        # Check if Gotchas section exists
        if "## Gotchas" not in memory:
            memory += "\n\n## Gotchas\n\n"

        # Create the entry
        entry = f"\n#### {repo}\n- **Problem**: {problem}\n- **Solution**: {solution}\n"

        # Avoid duplicates - check if this exact entry exists
        if problem in memory and solution in memory:
            return  # Already exists

        # Add entry after Gotchas header
        gotchas_idx = memory.find("## Gotchas")
        if gotchas_idx != -1:
            # Find end of header (next newline after ## Gotchas)
            insert_idx = memory.find("\n", gotchas_idx) + 1
            memory = memory[:insert_idx] + entry + memory[insert_idx:]

        self.memory_path.write_text(memory, encoding="utf-8")


# Singleton instance
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get the singleton MemoryManager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager

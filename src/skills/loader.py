"""
Skill Loader - Load skills from markdown files.

This implements the openclaw-style markdown-driven architecture.
Skills are stored as .md files, and the agent reads them to determine
how to execute tasks.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from dataclasses import dataclass


@dataclass
class Skill:
    """A skill loaded from markdown."""
    name: str
    type: str
    agent: str
    priority: str
    content: str
    metadata: dict[str, Any]

    def get_section(self, section_name: str) -> str:
        """Extract a section from the skill markdown."""
        pattern = rf"## {section_name}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, self.content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""


class SkillLoader:
    """Load skills from markdown files in the skills directory."""

    def __init__(self, skills_dir: Path | None = None):
        """
        Initialize the skill loader.

        Args:
            skills_dir: Directory containing skill markdown files.
                       Defaults to ../skills relative to this file.
        """
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent.parent / "skills"
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._load_all_skills()

    def _load_all_skills(self):
        """Load all skills from markdown files."""
        if not self.skills_dir.exists():
            return

        for skill_path in self.skills_dir.rglob("SKILL.md"):
            skill = self._load_skill(skill_path)
            if skill:
                self._skills[skill.name] = skill

    def _load_skill(self, path: Path) -> Skill | None:
        """Load a single skill from a markdown file."""
        try:
            content = path.read_text(encoding="utf-8")

            # Extract metadata from YAML block
            metadata = {}
            metadata_match = re.search(r"```yaml\n(.*?)```", content, re.DOTALL)
            if metadata_match:
                yaml_content = metadata_match.group(1)
                for line in yaml_content.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()

            # Get skill name from metadata or directory name
            name = metadata.get("name") or path.parent.name

            return Skill(
                name=name,
                type=metadata.get("type", "general"),
                agent=metadata.get("agent", "general"),
                priority=metadata.get("priority", "medium"),
                content=content,
                metadata=metadata,
            )
        except Exception as e:
            print(f"Warning: Failed to load skill from {path}: {e}")
            return None

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_skills_by_type(self, skill_type: str) -> list[Skill]:
        """Get all skills of a specific type."""
        return [s for s in self._skills.values() if s.type == skill_type]

    def get_skills_for_agent(self, agent_name: str) -> list[Skill]:
        """Get all skills for a specific agent."""
        return [s for s in self._skills.values() if s.agent == agent_name]

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        return list(self._skills.keys())

    def get_tools_md(self) -> str:
        """Load and return the TOOLS.md content."""
        tools_path = self.skills_dir.parent / "TOOLS.md"
        if tools_path.exists():
            return tools_path.read_text(encoding="utf-8")
        return ""

    def get_agents_md(self) -> str:
        """Load and return the AGENTS.md content."""
        agents_path = self.skills_dir.parent / "AGENTS.md"
        if agents_path.exists():
            return agents_path.read_text(encoding="utf-8")
        return ""

    def get_soul_md(self) -> str:
        """Load and return the SOUL.md content."""
        soul_path = self.skills_dir.parent / "SOUL.md"
        if soul_path.exists():
            return soul_path.read_text(encoding="utf-8")
        return ""


# Global skill loader instance
_skill_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    """Get the global skill loader instance."""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader

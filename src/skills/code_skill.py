"""
Code Skill - Intelligent code editing and analysis.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.skills.base import Skill
from src.config import get_settings
from src.memory.manager import MemoryManager


class CodeSkill(Skill):
    """Skill for intelligent code editing and analysis."""

    def __init__(self, claude: Anthropic, memory: MemoryManager):
        super().__init__(claude, memory)
        self.settings = get_settings()

    async def edit_file(self, file_path: str, instruction: str) -> dict[str, Any]:
        """
        Edit a file based on instruction.

        Uses incremental editing rather than full file replacement.
        """
        # Resolve file path
        full_path = self._resolve_path(file_path)
        if not full_path or not full_path.exists():
            return {
                "status": "error",
                "response": f"File not found: {file_path}",
            }

        try:
            # Read current content
            current_content = full_path.read_text(encoding="utf-8")

            # Detect file type for syntax
            file_ext = full_path.suffix
            language = self._detect_language(file_ext)

            # Analyze code structure
            structure = await self._analyze_structure(current_content, language)

            # Build prompt for incremental edit
            prompt = f"""You are editing a file to implement a change.

## File: {file_path}
## Language: {language}

## Current Code Structure:
{structure}

## Current File Content:
```
{current_content[:5000]}
{"...(truncated)" if len(current_content) > 5000 else ""}
```

## Instruction:
{instruction}

## Task:
Provide the changes needed. Respond in one of two formats:

1. For small changes, use SEARCH/REPLACE format:
```
SEARCH:
<exact code to find>
REPLACE:
<new code>
```

2. For larger changes, provide the complete modified section.

Important:
- Only modify what's necessary
- Preserve existing code style
- Be precise with SEARCH matches

Respond with the changes only, no explanations."""

            response = self.claude.messages.create(
                model=self.settings.default_model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Apply changes
            new_content, changes_made = self._apply_changes(current_content, content)

            if changes_made:
                # Write the modified content
                full_path.write_text(new_content, encoding="utf-8")

                return {
                    "status": "success",
                    "response": f"Edited {file_path}. Changes applied: {changes_made}",
                    "data": {
                        "file": str(full_path),
                        "changes": changes_made,
                    },
                }
            else:
                return {
                    "status": "partial",
                    "response": f"Could not parse changes from response. Please be more specific.",
                    "data": {"raw_response": content},
                }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to edit file: {str(e)}",
                "error": str(e),
            }

    async def analyze_file(self, file_path: str) -> dict[str, Any]:
        """Analyze a file's structure and purpose."""
        full_path = self._resolve_path(file_path)
        if not full_path or not full_path.exists():
            return {
                "status": "error",
                "response": f"File not found: {file_path}",
            }

        try:
            content = full_path.read_text(encoding="utf-8")
            file_ext = full_path.suffix
            language = self._detect_language(file_ext)

            structure = await self._analyze_structure(content, language)

            return {
                "status": "success",
                "response": f"Analysis of {file_path}:\n\n```\n{structure}\n```",
                "data": {
                    "file": str(full_path),
                    "language": language,
                    "lines": len(content.splitlines()),
                    "structure": structure,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "response": f"Failed to analyze file: {str(e)}",
                "error": str(e),
            }

    def _resolve_path(self, file_path: str) -> Path | None:
        """Resolve a file path relative to repos base path."""
        # Try as absolute path
        p = Path(file_path)
        if p.exists():
            return p

        # Try relative to repos base
        p = self.settings.repos_base_path / file_path
        if p.exists():
            return p

        # Try to find in any repo
        for repo_dir in self.settings.repos_base_path.iterdir():
            if repo_dir.is_dir() and (repo_dir / ".git").exists():
                p = repo_dir / file_path
                if p.exists():
                    return p

        return None

    def _detect_language(self, file_ext: str) -> str:
        """Detect programming language from file extension."""
        lang_map = {
            ".py": "Python",
            ".java": "Java",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C",
            ".hpp": "C++",
            ".cs": "C#",
            ".php": "PHP",
            ".rb": "Ruby",
            ".kt": "Kotlin",
            ".swift": "Swift",
            ".md": "Markdown",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".xml": "XML",
            ".sql": "SQL",
            ".sh": "Shell",
            ".bash": "Bash",
        }
        return lang_map.get(file_ext.lower(), "Unknown")

    async def _analyze_structure(self, content: str, language: str) -> str:
        """Analyze code structure using Claude."""
        prompt = f"""Analyze the structure of this {language} code.

Provide a brief summary of:
- Classes/functions defined
- Main purpose of the code
- Any notable patterns or issues

Code:
```
{content[:2000]}
{"...(truncated)" if len(content) > 2000 else ""}
```

Be concise."""

        try:
            response = self.claude.messages.create(
                model=self.settings.default_model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception:
            return "Structure analysis unavailable"

    def _apply_changes(self, original: str, response: str) -> tuple[str, str]:
        """Apply changes from SEARCH/REPLACE format."""
        changes_made = "No changes detected"

        # Try SEARCH/REPLACE format
        if "SEARCH:" in response and "REPLACE:" in response:
            search_match = re.search(r"SEARCH:\n```\n(.*?)\n```", response, re.DOTALL)
            replace_match = re.search(r"REPLACE:\n```\n(.*?)\n```", response, re.DOTALL)

            if search_match and replace_match:
                search_text = search_match.group(1)
                replace_text = replace_match.group(1)

                if search_text in original:
                    new_content = original.replace(search_text, replace_text, 1)
                    changes_made = f"Replaced block of {len(search_text)} characters"
                    return new_content, changes_made

        # Try simple SEARCH/REPLACE without code blocks
        if "SEARCH:" in response and "REPLACE:" in response:
            parts = response.split("REPLACE:")
            if len(parts) >= 2:
                search_part = parts[0].split("SEARCH:")[1].strip()
                replace_part = parts[1].strip()

                if search_part in original:
                    new_content = original.replace(search_part, replace_part, 1)
                    changes_made = f"Replaced '{search_part[:30]}...'"
                    return new_content, changes_made

        # Fallback: try to extract code block as full file
        code_block_match = re.search(r"```\w*\n(.*?)\n```", response, re.DOTALL)
        if code_block_match:
            new_content = code_block_match.group(1)
            changes_made = "Full file replacement"
            return new_content, changes_made

        return original, changes_made

    async def execute(self, action: str = "edit", **kwargs) -> dict[str, Any]:
        """Execute a code action."""
        if action == "edit":
            return await self.edit_file(
                kwargs.get("file", ""),
                kwargs.get("instruction", ""),
            )
        elif action == "analyze":
            return await self.analyze_file(kwargs.get("file", ""))
        else:
            return {
                "status": "error",
                "response": f"Unknown action: {action}",
            }

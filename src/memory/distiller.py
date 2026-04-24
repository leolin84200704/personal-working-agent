"""
Memory Distiller - Extract generalizable insights from short-term ticket records.

Uses LLM to distill short-term memory (per-ticket notes) into long-term
knowledge (knowledge/*.md, MEMORY.md). Supports single-ticket distillation,
cross-ticket pattern review, and knowledge compression.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.config import get_settings
from src.memory.manager import MemoryManager, get_memory_manager
from src.memory.security_scanner import SecurityViolation, get_scanner
from src.utils.logger import get_logger

logger = get_logger("memory.distiller")

from src.config import get_settings as _get_settings

def _model() -> str:
    return _get_settings().default_model

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

DISTILL_SYSTEM_PROMPT = """\
You are a knowledge distillation system for a software engineering team working \
on Laboratory Information System (LIS) projects.

Your job is to read short-term memory from a completed ticket and extract \
GENERALIZABLE insights -- lessons that will help the team in future tickets.

Rules:
- Focus on actionable insights, not ticket-specific summaries.
- Ignore ticket IDs, dates, and one-off details that will never recur.
- Categorize each insight into exactly one of these categories:
  pm_patterns   - PM-specific communication patterns (e.g. "PM X's tickets always need Y")
  technical     - Technical knowledge about repos, APIs, DB schemas, etc.
  repo_patterns - Repo-specific build/deploy/config patterns
  process       - Process improvements, workflow observations

Output valid JSON with this schema:
{
  "insights": [
    {
      "category": "technical",
      "title": "Short title",
      "content": "Markdown-formatted insight ready to append to a knowledge file.",
      "target_file": "patterns.md"
    }
  ]
}

target_file must be one of: emr-integration.md, repos.md, patterns.md, \
ticket-routing.md, MEMORY.md.
Choose the file that best matches the insight's topic.
If unsure, use MEMORY.md.
"""

CROSS_REVIEW_SYSTEM_PROMPT = """\
You are a cross-ticket pattern analysis system for a software engineering team \
working on Laboratory Information System (LIS) projects.

You will receive short-term memory extracts from multiple recent tickets. \
Your job is to find RECURRING themes, systemic issues, and cross-cutting \
patterns that are not visible from any single ticket alone.

Look for:
- Recurring technical problems (same bug class, same misconfiguration)
- PM-specific patterns (e.g. "PM X's tickets consistently lack field Y")
- Repo hotspots (same files keep needing changes)
- Process gaps (same manual step keeps being forgotten)
- Opportunities for automation or documentation

Output valid JSON with this schema:
{
  "patterns": [
    {
      "title": "Short title",
      "description": "Detailed description of the cross-cutting pattern.",
      "evidence": ["ticket-A had X", "ticket-B also had X"],
      "recommendation": "Actionable recommendation.",
      "target_file": "patterns.md"
    }
  ]
}

target_file must be one of: emr-integration.md, repos.md, patterns.md, \
ticket-routing.md, MEMORY.md.
"""

COMPRESS_SYSTEM_PROMPT = """\
You are a knowledge compression system. You will receive the contents of a \
markdown knowledge file that has grown too large.

Your job is to:
1. Remove duplicate or near-duplicate entries.
2. Merge entries that cover the same topic.
3. Remove outdated information that has been superseded.
4. Preserve ALL unique, actionable knowledge.
5. Keep the same markdown structure (headings, bullet points).

Output the compressed markdown directly. Do NOT wrap it in code fences.
Do NOT add commentary -- output ONLY the compressed markdown.
"""


class MemoryDistiller:
    """Distills short-term ticket memory into long-term knowledge."""

    def __init__(self, claude_client: Anthropic):
        self.claude = claude_client
        self.settings = get_settings()
        self.memory = get_memory_manager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def distill_ticket(self, ticket_id: str) -> str:
        """
        Extract generalizable insights from a ticket's short-term memory
        and append them to long-term memory (knowledge files or MEMORY.md).

        Uses Haiku for cost-efficiency.
        Returns summary of what was distilled.
        """
        stm_content = self._read_stm_file(ticket_id)
        if not stm_content:
            return f"No short-term memory found for ticket {ticket_id}."

        prompt = (
            f"Here is the short-term memory for ticket {ticket_id}:\n\n"
            f"---\n{stm_content}\n---\n\n"
            "Extract generalizable insights from this ticket. "
            "Return JSON as specified."
        )

        raw = self._call_llm(
            prompt, system=DISTILL_SYSTEM_PROMPT, model=_model(), max_tokens=2048
        )
        insights = self._parse_json(raw)

        if not insights or "insights" not in insights:
            logger.warning("Failed to parse distillation output for %s", ticket_id)
            return f"Failed to parse distillation output for {ticket_id}."

        saved_count = 0
        summaries: list[str] = []

        for item in insights["insights"]:
            category = item.get("category", "unknown")
            title = item.get("title", "Untitled")
            content = item.get("content", "")
            target = item.get("target_file", "MEMORY.md")

            if not content.strip():
                continue

            section_header = f"## Distilled - {category}"
            entry = f"### {title}\n{content}"

            if target == "MEMORY.md":
                self._append_to_memory_md(section_header, entry)
            else:
                self._append_to_knowledge(target, section_header, entry)

            saved_count += 1
            summaries.append(f"  - [{category}] {title} -> {target}")

        summary = (
            f"Distilled {saved_count} insight(s) from ticket {ticket_id}:\n"
            + "\n".join(summaries)
        )
        logger.info(summary)
        return summary

    def cross_ticket_review(self, last_n: int = 5) -> str:
        """
        Review the last N completed tickets for cross-cutting patterns.

        Uses Sonnet for deeper analysis.
        Returns the patterns found and where they were saved.
        """
        stm_dir = self.settings.storage_path / "short_term_memory"
        if not stm_dir.exists():
            return "No short-term memory directory found."

        md_files = sorted(stm_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not md_files:
            return "No short-term memory files found."

        files_to_review = md_files[:last_n]
        extracts: list[str] = []

        for f in files_to_review:
            ticket_id = f.stem
            content = f.read_text(encoding="utf-8")
            # Extract Lessons Learned section if present, otherwise use full content
            lessons = self._extract_section(content, "Lessons Learned")
            extract = lessons if lessons else content
            # Truncate individual extracts to keep prompt manageable
            if len(extract) > 3000:
                extract = extract[:3000] + "\n...(truncated)"
            extracts.append(f"## Ticket: {ticket_id}\n{extract}")

        combined = "\n\n---\n\n".join(extracts)
        prompt = (
            f"Here are short-term memory extracts from {len(files_to_review)} recent tickets:\n\n"
            f"{combined}\n\n"
            "Identify cross-cutting patterns. Return JSON as specified."
        )

        raw = self._call_llm(
            prompt, system=CROSS_REVIEW_SYSTEM_PROMPT, model=_model(), max_tokens=4096
        )
        result = self._parse_json(raw)

        if not result or "patterns" not in result:
            logger.warning("Failed to parse cross-ticket review output")
            return "Failed to parse cross-ticket review output."

        saved_count = 0
        summaries: list[str] = []

        for pattern in result["patterns"]:
            title = pattern.get("title", "Untitled")
            description = pattern.get("description", "")
            recommendation = pattern.get("recommendation", "")
            target = pattern.get("target_file", "patterns.md")

            if not description.strip():
                continue

            entry_parts = [f"### {title}", description]
            if recommendation:
                entry_parts.append(f"\n**Recommendation:** {recommendation}")

            entry = "\n".join(entry_parts)
            section_header = "## Cross-Ticket Patterns"

            if target == "MEMORY.md":
                self._append_to_memory_md(section_header, entry)
            else:
                self._append_to_knowledge(target, section_header, entry)

            saved_count += 1
            summaries.append(f"  - {title} -> {target}")

        summary = (
            f"Found {saved_count} cross-ticket pattern(s) from {len(files_to_review)} tickets:\n"
            + "\n".join(summaries)
        )
        logger.info(summary)
        return summary

    def compress_knowledge(self, max_chars: int = 50000) -> str:
        """
        If MEMORY.md or knowledge files exceed max_chars, use LLM to reorganize.

        Uses Haiku for compression.
        Returns summary of what was compressed.
        """
        compressed_files: list[str] = []

        # 1. Check MEMORY.md
        memory_path = self.settings.agent_root / "MEMORY.md"
        if memory_path.exists():
            content = memory_path.read_text(encoding="utf-8")
            if len(content) > max_chars:
                logger.info(
                    "MEMORY.md is %d chars (max %d), compressing...",
                    len(content), max_chars,
                )
                new_content = self._compress_file(content, "MEMORY.md", max_chars)
                if new_content and len(new_content) < len(content):
                    try:
                        get_scanner().scan(
                            new_content,
                            context="distiller:compress_knowledge:MEMORY.md",
                        )
                    except SecurityViolation as e:
                        logger.warning(
                            "Rejected compressed MEMORY.md: %s", e.category
                        )
                    else:
                        memory_path.write_text(new_content, encoding="utf-8")
                        compressed_files.append(
                            f"MEMORY.md: {len(content)} -> {len(new_content)} chars"
                        )

        # 2. Check each knowledge/*.md file
        knowledge_dir = self.settings.agent_root / "knowledge"
        if knowledge_dir.exists():
            for md_file in sorted(knowledge_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                if len(content) > max_chars:
                    logger.info(
                        "%s is %d chars (max %d), compressing...",
                        md_file.name, len(content), max_chars,
                    )
                    new_content = self._compress_file(content, md_file.name, max_chars)
                    if new_content and len(new_content) < len(content):
                        try:
                            get_scanner().scan(
                                new_content,
                                context=f"distiller:compress_knowledge:{md_file.name}",
                            )
                        except SecurityViolation as e:
                            logger.warning(
                                "Rejected compressed %s: %s",
                                md_file.name,
                                e.category,
                            )
                        else:
                            md_file.write_text(new_content, encoding="utf-8")
                            compressed_files.append(
                                f"{md_file.name}: {len(content)} -> {len(new_content)} chars"
                            )

        if not compressed_files:
            return f"All files are within the {max_chars}-char limit. No compression needed."

        summary = "Compressed files:\n" + "\n".join(f"  - {f}" for f in compressed_files)
        logger.info(summary)
        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        prompt: str,
        system: str = DISTILL_SYSTEM_PROMPT,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Helper to call Claude with a prompt and explicit system prompt."""
        if model is None:
            model = _model()
        try:
            response = self.claude.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error("LLM call failed (model=%s): %s", model, e)
            return ""

    def _compress_file(self, content: str, filename: str, max_chars: int) -> str:
        """Compress a single file's content using LLM."""
        prompt = (
            f"The following is the contents of `{filename}` ({len(content)} chars). "
            f"Please compress it to under {max_chars} chars while preserving all "
            f"unique, actionable knowledge.\n\n"
            f"---\n{content}\n---"
        )
        return self._call_llm(
            prompt,
            system=COMPRESS_SYSTEM_PROMPT,
            model=_model(),
            max_tokens=max_chars // 3,  # rough token estimate
        )

    def _read_stm_file(self, ticket_id: str) -> str:
        """Read a short-term memory file."""
        stm_path = self.settings.storage_path / "short_term_memory" / f"{ticket_id}.md"
        if stm_path.exists():
            return stm_path.read_text(encoding="utf-8")
        return ""

    def _append_to_knowledge(self, file_name: str, section: str, content: str) -> None:
        """Append content to a knowledge file under a section header."""
        # Security guard: reject distilled content that contains prompt
        # injection, credentials, or exfiltration payloads before writing.
        try:
            get_scanner().scan(
                f"{section}\n{content}",
                context=f"distiller:_append_to_knowledge:{file_name}",
            )
        except SecurityViolation as e:
            logger.warning(
                "Rejected distilled insight for %s: %s", file_name, e.category
            )
            return

        knowledge_dir = self.settings.agent_root / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        file_path = knowledge_dir / file_name

        existing = ""
        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")

        # Check for duplicate content (simple substring check)
        if content.strip() in existing:
            logger.debug("Skipping duplicate content in %s", file_name)
            return

        if section in existing:
            # Append under the existing section
            section_idx = existing.index(section)
            # Find end of section header line
            insert_idx = existing.index("\n", section_idx) + 1
            updated = existing[:insert_idx] + "\n" + content + "\n" + existing[insert_idx:]
        else:
            # Add new section at end of file
            updated = existing.rstrip() + f"\n\n{section}\n\n{content}\n"

        file_path.write_text(updated, encoding="utf-8")
        logger.info("Appended to %s under '%s'", file_name, section)

    def _append_to_memory_md(self, section: str, content: str) -> None:
        """Append content to MEMORY.md under a section header."""
        try:
            get_scanner().scan(
                f"{section}\n{content}",
                context="distiller:_append_to_memory_md",
            )
        except SecurityViolation as e:
            logger.warning(
                "Rejected distilled insight for MEMORY.md: %s", e.category
            )
            return

        memory_path = self.settings.agent_root / "MEMORY.md"
        existing = ""
        if memory_path.exists():
            existing = memory_path.read_text(encoding="utf-8")

        # Check for duplicate content
        if content.strip() in existing:
            logger.debug("Skipping duplicate content in MEMORY.md")
            return

        if section in existing:
            section_idx = existing.index(section)
            insert_idx = existing.index("\n", section_idx) + 1
            updated = existing[:insert_idx] + "\n" + content + "\n" + existing[insert_idx:]
        else:
            updated = existing.rstrip() + f"\n\n{section}\n\n{content}\n"

        memory_path.write_text(updated, encoding="utf-8")
        logger.info("Appended to MEMORY.md under '%s'", section)

    @staticmethod
    def _extract_section(content: str, heading: str) -> str:
        """Extract a markdown section by heading text (any level)."""
        lines = content.split("\n")
        capturing = False
        captured: list[str] = []
        heading_level = 0

        for line in lines:
            stripped = line.strip()
            if not capturing:
                if heading.lower() in stripped.lower() and stripped.startswith("#"):
                    capturing = True
                    heading_level = len(stripped) - len(stripped.lstrip("#"))
                    captured.append(line)
            else:
                # Stop at same or higher level heading
                if stripped.startswith("#"):
                    current_level = len(stripped) - len(stripped.lstrip("#"))
                    if current_level <= heading_level:
                        break
                captured.append(line)

        return "\n".join(captured).strip()

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        """Parse JSON from LLM output, handling code fences."""
        if not text:
            return None

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code fences
        if "```json" in text:
            try:
                json_str = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        if "```" in text:
            try:
                json_str = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        # Try finding JSON object in text
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            pass

        return None


# ---------------------------------------------------------------------------
# Tool definitions for Anthropic tool_use
# ---------------------------------------------------------------------------

DISTILL_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "stm_distill",
        "description": (
            "蒸餾短期記憶到長期記憶。"
            "Extract generalizable insights from a ticket's short-term memory "
            "and save them to the appropriate long-term knowledge files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The Jira ticket ID (e.g. LIS-1234) whose short-term memory to distill.",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "cross_ticket_review",
        "description": (
            "跨 ticket 模式分析。"
            "Review recent completed tickets for cross-cutting patterns, "
            "recurring issues, and systemic opportunities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "last_n": {
                    "type": "integer",
                    "description": "Number of recent tickets to review. Defaults to 5.",
                    "default": 5,
                },
            },
            "required": [],
        },
    },
    {
        "name": "compress_knowledge",
        "description": (
            "壓縮整理過長的知識庫。"
            "Compress and reorganize knowledge files (MEMORY.md and knowledge/*.md) "
            "that have grown too large, removing duplicates and merging related entries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum character count per file before compression triggers. Defaults to 50000.",
                    "default": 50000,
                },
            },
            "required": [],
        },
    },
]

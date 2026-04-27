"""
Skill Generator - Hermes-style procedural memory.

Generates reusable skill markdown files from completed STM tickets that
contain a Lessons Learned section ("learn from successful execution"),
and supports patch-style updates to existing skills ("self-improvement
during execution").

Design notes:
- LLM call is delegated to the `claude` CLI via subprocess so this module
  can run without the Anthropic SDK in the path. The contract matches the
  spec: `claude -p --model claude-sonnet-4-6`.
- Every write goes through `security_scanner.scan()` (fail-closed).
- Naming: `skills/{category}/{slug}.md` to fit the existing skill layout.
- `patch_skill` is a precise string replace; on miss it returns False so
  callers can fall back to regenerate.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from src.memory.manager import MemoryManager, get_memory_manager
from src.memory.security_scanner import SecurityViolation, get_scanner
from src.utils.logger import get_logger

logger = get_logger("memory.skill_generator")


SKILL_CATEGORIES: tuple[str, ...] = (
    "emr_integration",
    "technical",
    "repo_patterns",
    "process",
    "debugging",
    "general",
)

DEFAULT_CATEGORY = "general"

# Maps STM frontmatter category to a skills/<dir>/ directory name.
# Skills directories on disk use kebab-case; we map underscored categories
# to existing on-disk directories to avoid creating duplicates.
CATEGORY_DIR_MAP: dict[str, str] = {
    "emr_integration": "emr-integration",
    "technical": "technical",
    "repo_patterns": "repo-patterns",
    "process": "process",
    "debugging": "debugging",
    "general": "general",
}


SKILL_GEN_SYSTEM_PROMPT = """\
You distill a completed engineering ticket's Lessons Learned section into a \
REUSABLE procedural skill -- a checklist a future agent can follow to handle \
similar tickets.

Output STRICT JSON only (no prose, no fences) with this schema:
{
  "name": "kebab-case-slug",
  "title": "Short human title",
  "category": "<one of: emr_integration|technical|repo_patterns|process|debugging|general>",
  "trigger": "Natural-language description of WHEN to use this skill (1-2 sentences). Used for keyword-based retrieval.",
  "when_to_use": ["bullet 1", "bullet 2"],
  "steps": ["step 1 (imperative)", "step 2", "..."],
  "pitfalls": ["pitfall 1", "..."],
  "references": ["TICKET-ID"]
}

Rules:
- name: lowercase kebab-case, max 40 chars, no special chars.
- steps: short imperative sentences. Aim 3-8 steps.
- Skip ticket-specific IDs/dates inside steps; keep them generalizable.
- If the ticket lacks reusable insight, return {"name": null}.
"""


class SkillGenerator:
    """Generate and patch Hermes-style procedural skill markdown files."""

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        skills_root: Path | None = None,
        cli_model: str = "claude-sonnet-4-6",
    ):
        self.memory = memory_manager or get_memory_manager()
        self.agent_root = self.memory.agent_root
        self.skills_root = Path(skills_root) if skills_root else self.agent_root / "skills"
        self.cli_model = cli_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_from_ticket(self, ticket_id: str) -> str | None:
        """Generate a skill markdown from a completed STM ticket.

        Preconditions:
          - STM file exists.
          - Frontmatter `status: completed`.
          - Lessons Learned section is non-trivial (>20 chars).

        Behavior:
          - On success, writes `skills/{category-dir}/{slug}.md` and
            returns the absolute path as str.
          - If a skill with the same slug already exists, attempts a
            patch (replace the Steps section) and returns its path.
          - On any failure (LLM, scan, IO), logs warning and returns None.
        """
        stm_path = self.memory.stm_dir / f"{ticket_id}.md"
        if not stm_path.exists():
            logger.warning("Skill gen: STM not found for %s", ticket_id)
            return None

        meta = self.memory.read_frontmatter(stm_path)
        if meta.get("status") != "completed":
            logger.debug("Skill gen: %s status != completed", ticket_id)
            return None

        content = stm_path.read_text(encoding="utf-8")
        lessons = self._extract_section(content, "Lessons Learned")
        if not lessons or len(lessons.strip()) < 20:
            logger.debug("Skill gen: %s no substantial Lessons Learned", ticket_id)
            return None

        # Build LLM prompt input.
        stm_category = meta.get("category", DEFAULT_CATEGORY)
        summary = meta.get("summary", "")
        prompt = (
            f"Ticket: {ticket_id}\n"
            f"Category hint: {stm_category}\n"
            f"Summary: {summary}\n\n"
            f"## Lessons Learned\n{lessons}\n\n"
            "Produce the JSON skill spec now."
        )

        raw = self._call_llm_cli(prompt, system=SKILL_GEN_SYSTEM_PROMPT)
        if not raw:
            logger.warning("Skill gen: empty LLM output for %s", ticket_id)
            return None

        spec = self._parse_json(raw)
        if not spec or not spec.get("name"):
            logger.warning("Skill gen: bad/empty spec for %s", ticket_id)
            return None

        skill_md = self._render_skill_md(spec, ticket_id=ticket_id)

        # Pre-write security scan.
        try:
            get_scanner().scan(
                skill_md,
                context=f"skill_generator:generate:{ticket_id}",
            )
        except SecurityViolation as e:
            logger.warning(
                "Skill gen: rejected by scanner (%s) for %s",
                e.category,
                ticket_id,
            )
            return None

        # Resolve target path.
        category = self._normalize_category(spec.get("category", stm_category))
        category_dir = CATEGORY_DIR_MAP.get(category, category)
        slug = self._slugify(spec["name"])
        target_dir = self.skills_root / category_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{slug}.md"

        if target_path.exists():
            # Existing skill -> attempt patch on the Steps section.
            new_steps = self._render_steps_section(spec.get("steps", []))
            existing = target_path.read_text(encoding="utf-8")
            old_steps = self._extract_steps_block(existing)
            if old_steps and old_steps.strip() != new_steps.strip():
                ok = self.patch_skill(str(target_path), old_steps, new_steps)
                if ok:
                    logger.info(
                        "Skill gen: patched existing %s from %s",
                        target_path.name,
                        ticket_id,
                    )
                    return str(target_path)
            logger.info(
                "Skill gen: skill already exists with no patch needed: %s",
                target_path.name,
            )
            return str(target_path)

        target_path.write_text(skill_md, encoding="utf-8")
        logger.info("Skill gen: wrote %s from %s", target_path, ticket_id)
        return str(target_path)

    def patch_skill(self, skill_path: str, old_section: str, new_section: str) -> bool:
        """Patch a skill markdown by exact-replace.

        Returns True on success, False if `old_section` is not found or
        the patched content fails the security scan.
        """
        path = Path(skill_path)
        if not path.exists():
            logger.warning("patch_skill: file not found: %s", skill_path)
            return False

        existing = path.read_text(encoding="utf-8")
        if old_section not in existing:
            logger.warning("patch_skill: old_section not found in %s", skill_path)
            return False

        patched = existing.replace(old_section, new_section, 1)

        try:
            get_scanner().scan(
                patched,
                context=f"skill_generator:patch:{path.name}",
            )
        except SecurityViolation as e:
            logger.warning(
                "patch_skill: rejected by scanner (%s) for %s",
                e.category,
                path.name,
            )
            return False

        # Bump `updated:` in frontmatter if present.
        patched = self._bump_updated(patched)

        path.write_text(patched, encoding="utf-8")
        logger.info("patch_skill: updated %s", path.name)
        return True

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_skill_md(self, spec: dict[str, Any], ticket_id: str) -> str:
        today = date.today().isoformat()
        slug = self._slugify(spec.get("name", "skill"))
        title = spec.get("title", slug.replace("-", " ").title())
        category = self._normalize_category(spec.get("category", DEFAULT_CATEGORY))
        trigger = (spec.get("trigger") or "").strip().replace("\n", " ")

        when_to_use = self._render_bullets(spec.get("when_to_use", []))
        steps_section = self._render_steps_section(spec.get("steps", []))
        pitfalls = self._render_bullets(spec.get("pitfalls", []))
        references = spec.get("references") or [ticket_id]
        ref_bullets = self._render_bullets(references)

        frontmatter = (
            "---\n"
            f"name: {slug}\n"
            "type: skill\n"
            f"category: {category}\n"
            "agent: lis-code-agent\n"
            f"trigger: {self._escape_yaml(trigger)}\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"source_ticket: {ticket_id}\n"
            "---\n"
        )

        body = (
            f"# {title}\n\n"
            f"## When to use\n{when_to_use}\n\n"
            f"{steps_section}\n\n"
            f"## Common pitfalls\n{pitfalls}\n\n"
            f"## References\n{ref_bullets}\n"
        )
        return frontmatter + body

    @staticmethod
    def _render_bullets(items: list[Any]) -> str:
        clean = [str(i).strip() for i in items if str(i).strip()]
        if not clean:
            return "- (none)"
        return "\n".join(f"- {i}" for i in clean)

    @staticmethod
    def _render_steps_section(steps: list[Any]) -> str:
        clean = [str(s).strip() for s in steps if str(s).strip()]
        if not clean:
            return "## Steps\n1. (no steps)"
        numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(clean))
        return f"## Steps\n{numbered}"

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

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
            else:
                if stripped.startswith("#"):
                    current_level = len(stripped) - len(stripped.lstrip("#"))
                    if current_level <= heading_level:
                        break
                captured.append(line)
        return "\n".join(captured).strip()

    @staticmethod
    def _extract_steps_block(content: str) -> str:
        """Return the `## Steps`...next-heading block (inclusive of header)."""
        m = re.search(r"(^|\n)## Steps\b", content)
        if not m:
            return ""
        start = m.start() + (1 if content[m.start()] == "\n" else 0)
        # Find next H2.
        rest = content[start + len("## Steps"):]
        next_m = re.search(r"\n## ", rest)
        end = start + len("## Steps") + (next_m.start() if next_m else len(rest))
        return content[start:end].rstrip()

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        """Parse JSON from LLM output, tolerating code fences and trailing prose."""
        if not text:
            return None
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            try:
                inner = text.split("```json", 1)[1].split("```", 1)[0].strip()
                return json.loads(inner)
            except (IndexError, json.JSONDecodeError):
                pass
        if "```" in text:
            try:
                inner = text.split("```", 1)[1].split("```", 1)[0].strip()
                return json.loads(inner)
            except (IndexError, json.JSONDecodeError):
                pass
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return None

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        s = name.lower().strip()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        s = s.strip("-")
        return s[:40] or "skill"

    @staticmethod
    def _normalize_category(cat: str) -> str:
        cat = (cat or "").strip().lower().replace("-", "_")
        if cat in SKILL_CATEGORIES:
            return cat
        return DEFAULT_CATEGORY

    @staticmethod
    def _escape_yaml(value: str) -> str:
        # Quote when the value contains characters YAML may parse oddly.
        if not value:
            return '""'
        if any(c in value for c in [":", "#", "\n", "\"", "'", "{", "}", "[", "]", ","]):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return value

    @staticmethod
    def _bump_updated(content: str) -> str:
        today = date.today().isoformat()
        if not content.startswith("---\n"):
            return content
        try:
            end = content.index("\n---", 3)
        except ValueError:
            return content
        head = content[: end]
        tail = content[end:]
        new_head = re.sub(
            r"(?m)^updated:\s*.*$",
            f"updated: {today}",
            head,
            count=1,
        )
        return new_head + tail

    # ------------------------------------------------------------------
    # LLM CLI
    # ------------------------------------------------------------------

    def _call_llm_cli(self, prompt: str, system: str) -> str:
        """Call the `claude -p` CLI. Returns "" on failure."""
        try:
            full_prompt = f"{system}\n\n---\n\n{prompt}"
            proc = subprocess.run(
                ["claude", "-p", "--model", self.cli_model],
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                logger.warning(
                    "claude CLI returned %s: %s",
                    proc.returncode,
                    (proc.stderr or "")[:200],
                )
                return ""
            return proc.stdout or ""
        except FileNotFoundError:
            logger.warning("claude CLI not found on PATH")
            return ""
        except subprocess.TimeoutExpired:
            logger.warning("claude CLI timed out")
            return ""
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("claude CLI invocation failed: %s", e)
            return ""


# Singleton convenience.
_generator: SkillGenerator | None = None


def get_skill_generator() -> SkillGenerator:
    global _generator
    if _generator is None:
        _generator = SkillGenerator()
    return _generator

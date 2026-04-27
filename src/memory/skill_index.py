"""
Skill Index - Keyword retrieval over Hermes-style procedural skills.

Loads all `skills/**/*.md` files, parses YAML frontmatter (specifically
`name`, `category`, `trigger`) plus the H1 title and "When to use" body,
and ranks them by keyword overlap with a query.

Why keyword-only:
- Procedural skills are short, well-titled, and trigger-tagged. Keyword
  overlap is sufficient and cheap. We deliberately avoid Chroma here so
  that the LoCoMo benchmark sandbox (which already holds a Chroma store
  for dialogue retrieval) is not double-loaded.

Usage in real ticket flow (Step 1 Retrieve):
    from src.memory.skill_index import find_relevant_skills
    skills = find_relevant_skills(ticket.summary, top_k=3)
    for s in skills:
        print(s["path"], s["score"])

LoCoMo note: dialogue benchmark samples do not need procedural skills.
This module is documented here for the v1 adapter so it can opt-in via
the `skills.enabled` config switch in v1_hermes.yaml.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from src.memory.manager import get_memory_manager
from src.utils.logger import get_logger

logger = get_logger("memory.skill_index")


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "or", "the", "to", "of", "in", "on", "for",
        "with", "is", "are", "was", "were", "be", "this", "that", "it",
        "as", "at", "by", "from", "but", "if", "then", "else", "so",
        "you", "we", "i", "they", "he", "she", "do", "does", "did",
    }
)


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _parse_skill_frontmatter(path: Path) -> dict[str, Any]:
    """Return frontmatter dict + extra fields parsed from body."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    meta: dict[str, Any] = {}
    body = content
    if content.startswith("---\n"):
        try:
            end = content.index("\n---", 3)
            yaml_str = content[4:end]
            parsed = yaml.safe_load(yaml_str) or {}
            if isinstance(parsed, dict):
                meta = parsed
            body = content[end + 4:]
        except (ValueError, yaml.YAMLError):
            body = content

    # H1 title from body
    title = ""
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("# "):
            title = s[2:].strip()
            break
    meta["_title"] = title

    # "When to use" snippet for keyword text.
    when = _extract_section(body, "When to use")
    meta["_when_to_use"] = when

    return meta


def _extract_section(body: str, heading: str) -> str:
    lines = body.split("\n")
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
                level = len(stripped) - len(stripped.lstrip("#"))
                if level <= heading_level:
                    break
            captured.append(line)
    return "\n".join(captured).strip()


def find_relevant_skills(
    query: str,
    top_k: int = 3,
    skills_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return up to `top_k` skill records ranked by keyword overlap.

    Each record:
        {
          "path": absolute_path_str,
          "name": str,
          "title": str,
          "category": str,
          "trigger": str,
          "score": int,
        }
    """
    root = Path(skills_root) if skills_root else (get_memory_manager().agent_root / "skills")
    if not root.exists():
        return []

    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return []

    candidates: list[dict[str, Any]] = []
    for md in root.rglob("*.md"):
        if md.name.startswith("_"):
            continue
        meta = _parse_skill_frontmatter(md)
        if not meta:
            continue

        # Build searchable bag: trigger (weight x3), title (x2), name (x2), when_to_use (x1).
        trigger = str(meta.get("trigger", ""))
        title = str(meta.get("_title", ""))
        name = str(meta.get("name", md.stem))
        when = str(meta.get("_when_to_use", ""))
        category = str(meta.get("category", ""))

        bag_tokens: list[str] = (
            _tokenize(trigger) * 3
            + _tokenize(title) * 2
            + _tokenize(name) * 2
            + _tokenize(when)
            + _tokenize(category)
        )
        if not bag_tokens:
            continue

        score = sum(1 for t in bag_tokens if t in query_tokens)
        if score == 0:
            continue

        candidates.append(
            {
                "path": str(md),
                "name": name,
                "title": title or name,
                "category": category,
                "trigger": trigger,
                "score": score,
            }
        )

    candidates.sort(key=lambda r: (-r["score"], r["name"]))
    return candidates[:top_k]

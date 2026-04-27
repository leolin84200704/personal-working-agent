"""
Short-Term Memory Manager - Per-ticket work records stored as markdown files.

Manages the creation, reading, updating, and semantic search of
per-ticket work loop records. Each ticket gets a structured markdown
file tracking analysis, decisions, code changes, failures, and lessons.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.memory.vector_store import VectorStore
from src.utils.logger import get_logger

logger = get_logger("memory.short_term")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHORT_TERM_MEMORY_DIR = "short_term_memory"

VALID_SECTIONS = [
    "Ticket Analysis",
    "Approaches Considered",
    "Decisions Made",
    "Code Changes",
    "Test Results",
    "User Feedback",
    "Failures",
    "Retrospective",
    "Lessons Learned",
]

STM_COLLECTION = "short_term_memory"

TICKET_TEMPLATE = """---
id: {ticket_id}
type: stm
category: technical
status: active
score: 0.00
base_weight: 0.9
created: {created_date}
updated: {created_date}
links: []
tags: [{ticket_id_lower}]
summary: "Work loop record for {ticket_id}"
---
# {ticket_id} - Work Loop Record

> Created: {created_at}
> Status: active

---

## Ticket Analysis
## Approaches Considered
## Decisions Made
## Code Changes
## Test Results
## User Feedback
## Failures
## Retrospective
## Lessons Learned
"""

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool_use schema)
# ---------------------------------------------------------------------------

STM_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "stm_create",
        "description": "建立新的短期記憶 - 為指定 ticket 建立一份工作紀錄檔案。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID, e.g. 'PROJ-1234'",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "stm_read",
        "description": "讀取短期記憶 - 取得指定 ticket 的完整工作紀錄。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID to read",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "stm_append",
        "description": "追加內容到指定區段 - 將新內容寫入 ticket 工作紀錄的特定 section。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID",
                },
                "section": {
                    "type": "string",
                    "description": "Section name to append to",
                    "enum": VALID_SECTIONS,
                },
                "content": {
                    "type": "string",
                    "description": "Content to append (markdown)",
                },
            },
            "required": ["ticket_id", "section", "content"],
        },
    },
    {
        "name": "stm_search",
        "description": "搜尋過去類似 ticket 的經驗 - 語意搜尋所有短期記憶，找出相關的過往工作紀錄。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (natural language)",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "stm_get_failures",
        "description": "取得某 ticket 的失敗紀錄 - 擷取 Failures section 的內容，方便快速回顧踩過的坑。",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID",
                },
            },
            "required": ["ticket_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# ShortTermMemoryManager
# ---------------------------------------------------------------------------


class ShortTermMemoryManager:
    """Manages per-ticket short-term memory files and their vector index."""

    def __init__(self, vector_store: VectorStore | None = None):
        settings = get_settings()
        self.base_path: Path = settings.storage_path / SHORT_TERM_MEMORY_DIR
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._vector_store = vector_store

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_path(self, ticket_id: str) -> Path:
        """Return the filesystem path for a ticket's memory file."""
        return self.base_path / f"{ticket_id}.md"

    def _ensure_stm_collection(self) -> None:
        """Ensure the VectorStore has the short_term_memory collection."""
        if self._vector_store is None:
            return
        if not hasattr(self._vector_store, STM_COLLECTION):
            coll = self._vector_store._get_collection(STM_COLLECTION)
            setattr(self._vector_store, STM_COLLECTION, coll)

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse markdown content into ``{section_name: content}`` dict.

        Splits on ``## <section>`` headers.  Content between one header and
        the next (or end-of-file) is captured, with leading/trailing
        whitespace stripped.
        """
        sections: dict[str, str] = {}
        # Match lines that start with "## " followed by a known section name
        pattern = re.compile(r"^## (.+)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        for i, match in enumerate(matches):
            section_name = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()
            # Remove HTML comments (template placeholders)
            section_content = re.sub(
                r"<!--.*?-->", "", section_content, flags=re.DOTALL
            ).strip()
            sections[section_name] = section_content

        return sections

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, ticket_id: str) -> str:
        """Create a new short-term memory file for a ticket.

        Returns:
            The absolute path to the created file as a string.
        """
        path = self._get_path(ticket_id)
        if path.exists():
            logger.info(f"STM file already exists for {ticket_id}: {path}")
            return str(path)

        now = datetime.now(timezone.utc)
        content = TICKET_TEMPLATE.format(
            ticket_id=ticket_id,
            ticket_id_lower=ticket_id.lower(),
            created_at=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            created_date=now.strftime("%Y-%m-%d"),
        )
        path.write_text(content, encoding="utf-8")
        logger.info(f"Created STM file: {path}")
        return str(path)

    def read(self, ticket_id: str) -> str:
        """Read the entire short-term memory file for a ticket.

        Returns:
            File contents, or an error message if not found.
        """
        path = self._get_path(ticket_id)
        if not path.exists():
            msg = f"No short-term memory found for ticket: {ticket_id}"
            logger.warning(msg)
            return msg
        return path.read_text(encoding="utf-8")

    def append_section(self, ticket_id: str, section: str, content: str) -> str:
        """Append *content* to a specific *section* in the ticket's memory.

        If the file does not exist, it is created first.

        Args:
            ticket_id: Ticket identifier.
            section: One of :data:`VALID_SECTIONS`.
            content: Markdown content to append.

        Returns:
            A status message.
        """
        if section not in VALID_SECTIONS:
            return (
                f"Invalid section '{section}'. "
                f"Valid sections: {', '.join(VALID_SECTIONS)}"
            )

        path = self._get_path(ticket_id)
        if not path.exists():
            self.create(ticket_id)

        file_content = path.read_text(encoding="utf-8")

        # Locate the section header
        header = f"## {section}"
        header_idx = file_content.find(header)
        if header_idx == -1:
            # Section header missing -- append at end of file
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            file_content += f"\n{header}\n\n### [{timestamp}]\n{content}\n"
            path.write_text(file_content, encoding="utf-8")
            logger.info(f"Appended to new section '{section}' for {ticket_id}")
            return f"Appended to '{section}' (new section) for {ticket_id}"

        # Find the end of this section (next ## header or EOF)
        next_header = re.search(
            r"^## ", file_content[header_idx + len(header) :], re.MULTILINE
        )
        if next_header:
            insert_pos = header_idx + len(header) + next_header.start()
        else:
            insert_pos = len(file_content)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        entry = f"\n### [{timestamp}]\n{content}\n"

        file_content = file_content[:insert_pos] + entry + file_content[insert_pos:]
        path.write_text(file_content, encoding="utf-8")
        logger.info(f"Appended to '{section}' for {ticket_id}")
        return f"Appended to '{section}' for {ticket_id}"

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Semantic search across all short-term memories with time-decay weighting.

        Args:
            query: Natural language search query.
            n_results: Maximum number of results.

        Returns:
            List of dicts with ``document``, ``metadata``, ``score`` keys,
            ranked by relevance * time-decay.
        """
        if self._vector_store is None:
            logger.warning("VectorStore not available; search skipped.")
            return []

        self._ensure_stm_collection()

        try:
            raw_results = self._vector_store.search(
                query=query,
                collection=STM_COLLECTION,
                n_results=n_results * 2,  # fetch extra to allow re-ranking
            )
        except Exception as e:
            logger.error(f"STM search failed: {e}")
            return []

        now = datetime.now(timezone.utc)

        scored: list[dict] = []
        for result in raw_results:
            meta = result.get("metadata", {})
            distance = result.get("distance", 1.0)

            # Compute age-based decay
            created_str = meta.get("created_at", "")
            age_days = 0
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(created_str)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    age_days = (now - created_dt).days
                except (ValueError, TypeError):
                    pass

            # decay: linearly decrease over 90 days, floor at 0.3
            decay = max(0.3, 1.0 - (age_days / 90))

            # ChromaDB distance is L2; smaller = more similar
            # Convert to a similarity score (inverse distance) then apply decay
            similarity = 1.0 / (1.0 + distance)
            score = similarity * decay

            scored.append(
                {
                    "document": result.get("document", ""),
                    "metadata": meta,
                    "score": round(score, 4),
                    "distance": distance,
                    "decay": round(decay, 4),
                }
            )

        # Sort by score descending, take top n_results
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n_results]

    def index_ticket(self, ticket_id: str) -> int:
        """Index a ticket's memory file into ChromaDB.

        Each non-empty section is stored as a separate document with metadata
        containing ``ticket_id``, ``section``, and ``created_at``.

        Returns:
            Number of sections indexed.
        """
        if self._vector_store is None:
            logger.warning("VectorStore not available; indexing skipped.")
            return 0

        self._ensure_stm_collection()

        path = self._get_path(ticket_id)
        if not path.exists():
            logger.warning(f"Cannot index: no STM file for {ticket_id}")
            return 0

        content = path.read_text(encoding="utf-8")
        sections = self._parse_sections(content)

        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        ids: list[str] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for section_name, section_content in sections.items():
            if not section_content:
                continue
            doc_text = f"[{ticket_id}] {section_name}: {section_content}"
            documents.append(doc_text)
            metadatas.append(
                {
                    "ticket_id": ticket_id,
                    "section": section_name,
                    "created_at": now_iso,
                }
            )
            ids.append(f"{ticket_id}::{section_name}")

        if not documents:
            logger.info(f"No non-empty sections to index for {ticket_id}")
            return 0

        try:
            self._vector_store.add(
                collection=STM_COLLECTION,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"Indexed {len(documents)} sections for {ticket_id}")
        except Exception as e:
            logger.error(f"Failed to index {ticket_id}: {e}")
            return 0

        return len(documents)

    def index_all(self) -> int:
        """Index all ticket memory files into ChromaDB.

        Returns:
            Total number of sections indexed across all tickets.
        """
        total = 0
        for md_file in sorted(self.base_path.glob("*.md")):
            ticket_id = md_file.stem
            total += self.index_ticket(ticket_id)
        logger.info(f"Indexed {total} total sections from all STM files")
        return total

    def list_tickets(self) -> list[dict]:
        """List all tickets that have short-term memory files.

        Returns:
            List of dicts with ``ticket_id``, ``path``, ``created_at``,
            and ``size_bytes``.
        """
        tickets: list[dict] = []
        for md_file in sorted(self.base_path.glob("*.md")):
            stat = md_file.stat()
            tickets.append(
                {
                    "ticket_id": md_file.stem,
                    "path": str(md_file),
                    "created_at": datetime.fromtimestamp(
                        stat.st_ctime, tz=timezone.utc
                    ).isoformat(),
                    "size_bytes": stat.st_size,
                }
            )
        return tickets

    def get_failures(self, ticket_id: str) -> str:
        """Extract just the Failures section from a ticket's memory.

        Returns:
            The failures content, or a message indicating no failures found.
        """
        content = self.read(ticket_id)
        if content.startswith("No short-term memory found"):
            return content

        sections = self._parse_sections(content)
        failures = sections.get("Failures", "")
        if not failures:
            return f"No failures recorded for {ticket_id}."
        return failures

    def decay_old(self, days: int = 30) -> list[str]:
        """Mark records older than *days* for compression/summarisation.

        Files older than the threshold are renamed with an ``_archived``
        suffix so the distiller (LLM) can summarise them later.  The
        original content is preserved -- nothing is deleted.

        Returns:
            List of affected ticket IDs.
        """
        affected: list[str] = []
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

        for md_file in self.base_path.glob("*.md"):
            if md_file.stem.endswith("_archived"):
                continue
            if md_file.stat().st_mtime < cutoff:
                ticket_id = md_file.stem
                archived_name = md_file.with_stem(f"{ticket_id}_archived")
                md_file.rename(archived_name)
                logger.info(
                    f"Archived old STM: {ticket_id} -> {archived_name.name}"
                )
                affected.append(ticket_id)

        if affected:
            logger.info(
                f"Archived {len(affected)} STM files older than {days} days"
            )
        return affected

"""
Memory Linker - Zettelkasten-style bidirectional cross-linking.

Discovers thematic connections between memory files and maintains
bidirectional links in YAML frontmatter. Linked files receive a
reference_boost in the scoring formula.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.memory.manager import MemoryManager
from src.utils.logger import get_logger

logger = get_logger("memory.linker")

# Keywords per category for link discovery
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "emr_integration": [
        "emr", "hl7", "ehr", "integration", "provider", "practice",
        "sftp", "bundle", "msh", "obr", "obx", "cerbo", "athena",
        "order_client", "ehr_integration", "result_transmission",
    ],
    "technical": [
        "grpc", "nestjs", "prisma", "typescript", "mysql", "postgresql",
        "kafka", "docker", "api", "controller", "service", "module",
    ],
    "repo_patterns": [
        "build", "deploy", "config", "env", "migration", "script",
        "pattern", "gotcha", "investigation",
    ],
    "pm_patterns": [
        "ticket", "routing", "pm", "kristine", "sprint", "jira",
    ],
}


class MemoryLinker:
    """Manages bidirectional cross-links between memory files."""

    def __init__(self, manager: MemoryManager | None = None):
        self.manager = manager or MemoryManager()

    def _get_all_files(self) -> list[Path]:
        """Get all memory files across STM and LTM tiers."""
        return self.manager.list_tier_files("stm") + self.manager.list_tier_files("ltm")

    def _extract_keywords(self, path: Path) -> set[str]:
        """Extract relevant keywords from a file's content and metadata."""
        meta = self.manager.read_frontmatter(path)
        content = path.read_text(encoding="utf-8").lower()

        keywords = set()
        tags = meta.get("tags", [])
        if isinstance(tags, list):
            keywords.update(t.lower() for t in tags)

        category = meta.get("category", "")
        cat_keywords = CATEGORY_KEYWORDS.get(category, [])
        for kw in cat_keywords:
            if kw in content:
                keywords.add(kw)

        return keywords

    def discover_links(self, min_overlap: int = 3) -> list[tuple[str, str]]:
        """Find pairs of files with overlapping themes.

        Returns list of (id_a, id_b) tuples for files that share
        at least min_overlap keywords.
        """
        files = self._get_all_files()
        file_keywords: dict[str, set[str]] = {}
        file_paths: dict[str, Path] = {}

        for f in files:
            meta = self.manager.read_frontmatter(f)
            file_id = meta.get("id", f.stem)
            file_keywords[file_id] = self._extract_keywords(f)
            file_paths[file_id] = f

        pairs: list[tuple[str, str]] = []
        ids = sorted(file_keywords.keys())

        for i, id_a in enumerate(ids):
            for id_b in ids[i + 1:]:
                overlap = file_keywords[id_a] & file_keywords[id_b]
                if len(overlap) >= min_overlap:
                    pairs.append((id_a, id_b))

        return pairs

    def add_link(self, file_a: Path, file_b: Path) -> bool:
        """Add a bidirectional link between two files.

        Returns True if any link was actually added (not already present).
        """
        meta_a = self.manager.read_frontmatter(file_a)
        meta_b = self.manager.read_frontmatter(file_b)
        id_a = meta_a.get("id", file_a.stem)
        id_b = meta_b.get("id", file_b.stem)

        changed = False

        links_a = meta_a.get("links", [])
        if not isinstance(links_a, list):
            links_a = []
        if id_b not in links_a:
            links_a.append(id_b)
            meta_a["links"] = sorted(set(links_a))
            self.manager.write_frontmatter(file_a, meta_a)
            changed = True

        links_b = meta_b.get("links", [])
        if not isinstance(links_b, list):
            links_b = []
        if id_a not in links_b:
            links_b.append(id_a)
            meta_b["links"] = sorted(set(links_b))
            self.manager.write_frontmatter(file_b, meta_b)
            changed = True

        if changed:
            logger.info("Linked %s <-> %s", id_a, id_b)
        return changed

    def remove_link(self, file_a: Path, file_b: Path) -> bool:
        """Remove a bidirectional link between two files."""
        meta_a = self.manager.read_frontmatter(file_a)
        meta_b = self.manager.read_frontmatter(file_b)
        id_a = meta_a.get("id", file_a.stem)
        id_b = meta_b.get("id", file_b.stem)

        changed = False

        links_a = meta_a.get("links", [])
        if id_b in links_a:
            links_a.remove(id_b)
            meta_a["links"] = links_a
            self.manager.write_frontmatter(file_a, meta_a)
            changed = True

        links_b = meta_b.get("links", [])
        if id_a in links_b:
            links_b.remove(id_a)
            meta_b["links"] = links_b
            self.manager.write_frontmatter(file_b, meta_b)
            changed = True

        return changed

    def get_link_graph(self) -> dict[str, list[str]]:
        """Build the full link graph from all memory files."""
        graph: dict[str, list[str]] = defaultdict(list)

        for f in self._get_all_files():
            meta = self.manager.read_frontmatter(f)
            file_id = meta.get("id", f.stem)
            links = meta.get("links", [])
            if isinstance(links, list):
                graph[file_id] = sorted(links)
            else:
                graph[file_id] = []

        return dict(graph)

    def count_incoming_links(self, file_id: str) -> int:
        """Count how many files link TO file_id."""
        count = 0
        for f in self._get_all_files():
            meta = self.manager.read_frontmatter(f)
            links = meta.get("links", [])
            if isinstance(links, list) and file_id in links:
                count += 1
        return count

    def auto_link_all(self, min_overlap: int = 3) -> int:
        """Discover and apply all cross-links. Returns count of new links added."""
        pairs = self.discover_links(min_overlap)
        files = self._get_all_files()
        path_map: dict[str, Path] = {}
        for f in files:
            meta = self.manager.read_frontmatter(f)
            path_map[meta.get("id", f.stem)] = f

        added = 0
        for id_a, id_b in pairs:
            if id_a in path_map and id_b in path_map:
                if self.add_link(path_map[id_a], path_map[id_b]):
                    added += 1

        logger.info("Auto-linked: %d new links from %d candidate pairs", added, len(pairs))
        return added

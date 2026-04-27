"""
Memory Consolidator - 7 atomic consolidation operations for the dreaming pipeline.

Operations:
  1. Extract   - Pull lasting insight from completed STM → LTM
  2. Merge     - Combine overlapping files into one
  3. Update    - Fix stale dates/facts in a file
  4. Resolve   - When new info contradicts old, trust newer
  5. Promote   - Pattern appears 3+ times in STM → create LTM file
  6. Archive   - Move completed low-score files to archive/
  7. Forget    - Delete truly irrelevant archived files (emr_integration exempt)
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.memory.manager import MemoryManager
from src.memory.scorer import MemoryScorer, ScoredFile
from src.utils.logger import get_logger

logger = get_logger("memory.consolidator")


class SignalType(str, Enum):
    COMPLETED = "completed"
    APPROACHING = "approaching"
    LASTING_INSIGHT = "lasting_insight"
    OVERLAP = "overlap"
    STALE = "stale"


class OpType(str, Enum):
    EXTRACT = "extract"
    MERGE = "merge"
    UPDATE = "update"
    RESOLVE = "resolve"
    PROMOTE = "promote"
    ARCHIVE = "archive"
    FORGET = "forget"


@dataclass
class Signal:
    file: Path
    signal_type: SignalType
    confidence: float
    details: str


@dataclass
class ConsolidationOp:
    op_type: OpType
    sources: list[Path]
    target: Path | None = None
    details: str = ""
    success: bool = False


@dataclass
class ConsolidationReport:
    date: str
    signals: list[Signal] = field(default_factory=list)
    operations: list[ConsolidationOp] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        ops_by_type = {}
        for op in self.operations:
            if op.success:
                ops_by_type[op.op_type.value] = ops_by_type.get(op.op_type.value, 0) + 1
        lines = [f"Dream {self.date}: {len(self.signals)} signals, {len(self.operations)} operations"]
        for op_type, count in sorted(ops_by_type.items()):
            lines.append(f"  {op_type}: {count}")
        return "\n".join(lines)


class MemoryConsolidator:
    """Executes consolidation operations on the 4-tier memory system."""

    def __init__(
        self,
        manager: MemoryManager | None = None,
        scorer: MemoryScorer | None = None,
    ):
        self.manager = manager or MemoryManager()
        self.scorer = scorer or MemoryScorer(self.manager)

    # ── Signal gathering (Phase 2 of dreaming) ────────────────────

    def gather_signals(self, today: date | None = None) -> list[Signal]:
        """Classify each STM file into signal types."""
        today = today or date.today()
        signals: list[Signal] = []

        stm_files = self.manager.list_tier_files("stm")
        for f in stm_files:
            meta = self.manager.read_frontmatter(f)
            status = meta.get("status", "active")
            updated = self.scorer._to_date_safe(meta.get("updated", today))
            age = (today - updated).days

            if status == "completed":
                content = f.read_text(encoding="utf-8")
                has_lessons = "## Lessons Learned" in content and len(
                    content.split("## Lessons Learned")[1].strip()
                ) > 20
                if has_lessons:
                    signals.append(Signal(f, SignalType.LASTING_INSIGHT, 0.8, "Completed with lessons"))
                else:
                    signals.append(Signal(f, SignalType.COMPLETED, 0.9, "Completed, no lasting insight"))
            elif age > 60:
                signals.append(Signal(f, SignalType.STALE, 0.7, f"Not updated in {age} days"))
            else:
                signals.append(Signal(f, SignalType.APPROACHING, 0.3, "Active ticket"))

        return signals

    # ── Consolidation operations (Phase 3 of dreaming) ────────────

    def extract_to_ltm(self, stm_path: Path) -> ConsolidationOp:
        """Op 1: Extract lasting insight from a completed STM into existing LTM file."""
        op = ConsolidationOp(OpType.EXTRACT, [stm_path])
        meta = self.manager.read_frontmatter(stm_path)
        content = stm_path.read_text(encoding="utf-8")

        lessons_section = self._extract_section(content, "Lessons Learned")
        if not lessons_section or len(lessons_section.strip()) < 20:
            op.details = "No substantial lessons to extract"
            return op

        category = meta.get("category", "technical")
        target_map = {
            "emr_integration": "emr-integration.md",
            "technical": "repos.md",
            "repo_patterns": "patterns.md",
            "pm_patterns": "ticket-routing.md",
            "process": "patterns.md",
        }
        target_name = target_map.get(category, "patterns.md")
        target_path = self.manager.ltm_dir / target_name

        if not target_path.exists():
            op.details = f"Target LTM file not found: {target_name}"
            return op

        existing = target_path.read_text(encoding="utf-8")
        ticket_id = meta.get("id", stm_path.stem)
        header = f"\n\n## Extracted from {ticket_id}\n\n"

        if ticket_id in existing:
            op.details = f"Already extracted from {ticket_id}"
            return op

        target_path.write_text(existing + header + lessons_section + "\n", encoding="utf-8")
        op.target = target_path
        op.details = f"Extracted to {target_name}"
        op.success = True
        logger.info("Extracted insights from %s to %s", ticket_id, target_name)

        # Hermes-style procedural-memory hook: try to generate a reusable
        # skill markdown from this completed STM. Failures (LLM error or
        # security scan reject) are non-fatal -- log and continue.
        try:
            from src.memory.skill_generator import get_skill_generator
            gen = get_skill_generator()
            skill_path = gen.generate_from_ticket(ticket_id)
            if skill_path:
                op.details = f"Extracted to {target_name}; skill -> {skill_path}"
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Skill generation hook failed for %s: %s", ticket_id, e)

        return op

    def merge_files(self, file_a: Path, file_b: Path) -> ConsolidationOp:
        """Op 2: Merge two overlapping files into one. Keeps file_a, deletes file_b."""
        op = ConsolidationOp(OpType.MERGE, [file_a, file_b], target=file_a)

        meta_a = self.manager.read_frontmatter(file_a)
        meta_b = self.manager.read_frontmatter(file_b)
        content_a = file_a.read_text(encoding="utf-8")
        content_b = file_b.read_text(encoding="utf-8")

        body_b = self._strip_frontmatter(content_b)
        merged_content = content_a.rstrip() + "\n\n---\n\n" + f"<!-- Merged from {file_b.stem} -->\n" + body_b

        links_a = set(meta_a.get("links", []))
        links_b = set(meta_b.get("links", []))
        links_a.update(links_b)
        links_a.discard(meta_a.get("id", ""))
        meta_a["links"] = sorted(links_a)
        meta_a["updated"] = date.today().isoformat()

        file_a.write_text(merged_content, encoding="utf-8")
        self.manager.write_frontmatter(file_a, meta_a)
        file_b.unlink()
        op.details = f"Merged {file_b.stem} into {file_a.stem}"
        op.success = True
        logger.info("Merged %s into %s", file_b.stem, file_a.stem)
        return op

    def update_file(self, path: Path) -> ConsolidationOp:
        """Op 3: Update stale metadata (bump updated date)."""
        op = ConsolidationOp(OpType.UPDATE, [path], target=path)
        meta = self.manager.read_frontmatter(path)
        meta["updated"] = date.today().isoformat()
        self.manager.write_frontmatter(path, meta)
        op.details = "Updated date"
        op.success = True
        return op

    def resolve_conflict(self, old_path: Path, new_content: str, reason: str) -> ConsolidationOp:
        """Op 4: Resolve contradiction by updating file content."""
        op = ConsolidationOp(OpType.RESOLVE, [old_path], target=old_path)
        meta = self.manager.read_frontmatter(old_path)

        old_content = old_path.read_text(encoding="utf-8")
        body = self._strip_frontmatter(old_content)
        resolved_body = body + f"\n\n> **Resolved ({date.today()}):** {reason}\n\n{new_content}\n"

        frontmatter_str = old_content[:old_content.index("\n---", 3) + 4]
        old_path.write_text(frontmatter_str + "\n" + resolved_body, encoding="utf-8")

        meta["updated"] = date.today().isoformat()
        self.manager.write_frontmatter(old_path, meta)
        op.details = f"Resolved: {reason}"
        op.success = True
        return op

    def promote_to_ltm(self, pattern_title: str, content: str, category: str) -> ConsolidationOp:
        """Op 5: Create a new LTM file from a recurring STM pattern."""
        slug = pattern_title.lower().replace(" ", "-").replace("/", "-")[:50]
        target = self.manager.ltm_dir / f"{slug}.md"
        op = ConsolidationOp(OpType.PROMOTE, [], target=target)

        if target.exists():
            op.details = f"LTM file already exists: {slug}.md"
            return op

        weight_map = {
            "emr_integration": 1.0, "technical": 0.9,
            "repo_patterns": 0.8, "pm_patterns": 0.7, "process": 0.6,
        }

        meta = {
            "id": slug,
            "type": "ltm",
            "category": category,
            "status": "active",
            "score": 0.0,
            "base_weight": weight_map.get(category, 0.8),
            "created": date.today().isoformat(),
            "updated": date.today().isoformat(),
            "links": [],
            "tags": [],
            "summary": pattern_title,
        }

        import yaml
        yaml_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()
        file_content = f"---\n{yaml_str}\n---\n# {pattern_title}\n\n{content}\n"
        target.write_text(file_content, encoding="utf-8")

        op.details = f"Promoted pattern to {slug}.md"
        op.success = True
        logger.info("Promoted pattern '%s' to LTM: %s", pattern_title, target)
        return op

    def archive_file(self, path: Path) -> ConsolidationOp:
        """Op 6: Move a file to archive/."""
        op = ConsolidationOp(OpType.ARCHIVE, [path])
        meta = self.manager.read_frontmatter(path)

        dest = self.manager.archive_dir / path.name
        if dest.exists():
            op.details = f"Already archived: {path.name}"
            return op

        shutil.move(str(path), str(dest))

        meta["status"] = "archived"
        meta["original_tier"] = meta.get("type", "stm")
        meta["type"] = "archive"
        meta["updated"] = date.today().isoformat()
        self.manager.write_frontmatter(dest, meta)

        op.target = dest
        op.details = f"Archived {path.name}"
        op.success = True
        logger.info("Archived %s to %s", path.name, dest)
        return op

    def forget_file(self, path: Path) -> ConsolidationOp:
        """Op 7: Permanently delete a file (emr_integration exempt unless forced)."""
        op = ConsolidationOp(OpType.FORGET, [path])
        meta = self.manager.read_frontmatter(path)

        if meta.get("category") == "emr_integration":
            op.details = "emr_integration category is exempt from auto-forget"
            return op

        path.unlink()
        op.details = f"Forgotten (deleted) {path.name}"
        op.success = True
        logger.info("Forgotten %s", path.name)
        return op

    # ── Full consolidation cycle (Phase 3 of dreaming) ────────────

    def consolidate(self, signals: list[Signal], today: date | None = None) -> ConsolidationReport:
        """Execute consolidation operations based on gathered signals."""
        today = today or date.today()
        report = ConsolidationReport(date=today.isoformat(), signals=signals)

        for signal in signals:
            if signal.signal_type == SignalType.LASTING_INSIGHT:
                op = self.extract_to_ltm(signal.file)
                report.operations.append(op)

        archive_candidates = self.scorer.get_archive_candidates(today)
        for scored in archive_candidates:
            op = self.archive_file(scored.path)
            report.operations.append(op)

        forget_candidates = self.scorer.get_forget_candidates(today)
        for scored in forget_candidates:
            op = self.forget_file(scored.path)
            report.operations.append(op)

        report.stats = self.scorer.get_stats(today)
        return report

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _extract_section(content: str, heading: str) -> str:
        """Extract a markdown section by heading."""
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
    def _strip_frontmatter(content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---\n"):
            end = content.index("\n---", 3)
            return content[end + 4:].lstrip("\n")
        return content

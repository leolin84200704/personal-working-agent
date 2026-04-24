"""
Memory Scorer - Deterministic importance scoring for all memory files.

Formula: score = (base_weight * recency_factor * reference_boost) / normalization

Where:
  base_weight    from YAML frontmatter (0.6 - 1.0)
  recency_factor e^(-days_since_update / half_life)
                 half_life = 30 (STM) | 180 (LTM)
  reference_boost 1.0 + (0.1 * incoming_link_count)
  normalization  8.0

Thresholds:
  active:  score >= 0.1
  archive: score < 0.1 AND age > 90 days
  forget:  score < 0.05 AND age > 180 days (emr_integration exempt)
"""
from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.memory.manager import MemoryManager
from src.utils.logger import get_logger

logger = get_logger("memory.scorer")

HALF_LIFE = {"stm": 30, "archive": 180}
LTM_FIXED_RECENCY = 0.99  # LTM knowledge/patterns barely decay — scored by base_weight x links
NORMALIZATION = 8.0
ARCHIVE_SCORE_THRESHOLD = 0.1
ARCHIVE_AGE_DAYS = 90
FORGET_SCORE_THRESHOLD = 0.05
FORGET_AGE_DAYS = 180
FORGET_EXEMPT_CATEGORIES = {"emr_integration"}


def _to_date(val: Any) -> date:
    """Coerce a frontmatter date value to a date object."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val[:10])
    return date.today()


class ScoredFile:
    """Scoring result for a single memory file."""

    def __init__(
        self,
        path: Path,
        meta: dict[str, Any],
        score: float,
        days_since_update: int,
    ):
        self.path = path
        self.meta = meta
        self.score = score
        self.days_since_update = days_since_update

    @property
    def id(self) -> str:
        return self.meta.get("id", self.path.stem)

    @property
    def tier(self) -> str:
        return self.meta.get("type", "stm")

    @property
    def category(self) -> str:
        return self.meta.get("category", "technical")

    @property
    def status(self) -> str:
        return self.meta.get("status", "active")

    @property
    def summary(self) -> str:
        return self.meta.get("summary", "")

    @property
    def should_archive(self) -> bool:
        if self.status == "archived":
            return False
        return (
            self.score < ARCHIVE_SCORE_THRESHOLD
            and self.days_since_update > ARCHIVE_AGE_DAYS
            and self.status == "completed"
        )

    @property
    def should_forget(self) -> bool:
        if self.category in FORGET_EXEMPT_CATEGORIES:
            return False
        return (
            self.score < FORGET_SCORE_THRESHOLD
            and self.days_since_update > FORGET_AGE_DAYS
        )


class MemoryScorer:
    """Scores memory files and rebuilds index tables."""

    def __init__(self, manager: MemoryManager | None = None):
        self.manager = manager or MemoryManager()

    @staticmethod
    def _to_date_safe(val: Any) -> date:
        """Public access to date coercion."""
        return _to_date(val)

    def _count_incoming_links(self, file_id: str, all_files: list[Path]) -> int:
        """Count how many files link TO file_id."""
        count = 0
        for f in all_files:
            meta = self.manager.read_frontmatter(f)
            links = meta.get("links", [])
            if file_id in links:
                count += 1
        return count

    def score_file(
        self,
        path: Path,
        today: date | None = None,
        all_files: list[Path] | None = None,
    ) -> ScoredFile:
        """Calculate importance score for a single file."""
        today = today or date.today()
        meta = self.manager.read_frontmatter(path)

        base_weight = float(meta.get("base_weight", 0.9))
        tier = meta.get("type", "stm")
        updated = _to_date(meta.get("updated", today))
        file_id = meta.get("id", path.stem)

        days_since = (today - updated).days

        if tier == "ltm":
            recency = LTM_FIXED_RECENCY
        else:
            half_life = HALF_LIFE.get(tier, 30)
            recency = math.exp(-days_since / half_life)

        if all_files:
            incoming = self._count_incoming_links(file_id, all_files)
        else:
            incoming = 0
        boost = 1.0 + (0.1 * incoming)

        score = round((base_weight * recency * boost) / NORMALIZATION, 4)

        return ScoredFile(
            path=path,
            meta=meta,
            score=score,
            days_since_update=days_since,
        )

    def score_tier(self, tier: str, today: date | None = None) -> list[ScoredFile]:
        """Score all files in a tier. Returns list sorted by score descending."""
        today = today or date.today()
        files = self.manager.list_tier_files(tier)
        if not files:
            return []

        all_files = (
            self.manager.list_tier_files("stm")
            + self.manager.list_tier_files("ltm")
            + self.manager.list_tier_files("archive")
        )

        results = []
        for f in files:
            scored = self.score_file(f, today=today, all_files=all_files)
            results.append(scored)

        results.sort(key=lambda s: s.score, reverse=True)
        return results

    def score_all(self, today: date | None = None) -> dict[str, list[ScoredFile]]:
        """Score every file in every tier."""
        today = today or date.today()
        return {
            "stm": self.score_tier("stm", today),
            "ltm": self.score_tier("ltm", today),
            "archive": self.score_tier("archive", today),
        }

    def update_scores_in_files(self, tier: str, today: date | None = None) -> int:
        """Recalculate scores and write them back to each file's frontmatter."""
        scored = self.score_tier(tier, today)
        count = 0
        for s in scored:
            old_score = s.meta.get("score", 0.0)
            if abs(float(old_score) - s.score) > 0.0001:
                s.meta["score"] = s.score
                self.manager.write_frontmatter(s.path, s.meta)
                count += 1
                logger.info("Updated score: %s %.4f -> %.4f", s.id, float(old_score), s.score)
        return count

    def rebuild_index(self, tier: str, today: date | None = None) -> Path:
        """Rebuild _index.md for a tier with current scores."""
        scored = self.score_tier(tier, today)
        today = today or date.today()

        index_paths = {
            "stm": self.manager.stm_index_path,
            "ltm": self.manager.ltm_index_path,
            "archive": self.manager.archive_index_path,
        }
        index_path = index_paths[tier]

        tier_names = {"stm": "Short-Term Memory", "ltm": "Long-Term Memory", "archive": "Archive"}

        lines = [
            f"# {tier_names[tier]} Index",
            "",
            "> Auto-generated by scoring engine. Do not edit manually.",
            f"> Last updated: {today.isoformat()}",
            "",
        ]

        if tier == "archive":
            lines.append("| Score | ID | Summary | Original Tier | Archived |")
            lines.append("|-------|-----|---------|---------------|----------|")
            for s in scored:
                lines.append(
                    f"| {s.score:.2f} | {s.id} | {s.summary} | {s.meta.get('original_tier', 'stm')} | {s.meta.get('updated', '')} |"
                )
        else:
            lines.append("| Score | ID | Summary | Status | Category | Updated |")
            lines.append("|-------|-----|---------|--------|----------|---------|")
            for s in scored:
                lines.append(
                    f"| {s.score:.2f} | {s.id} | {s.summary} | {s.status} | {s.category} | {s.meta.get('updated', '')} |"
                )

        lines.append("")
        index_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Rebuilt %s index: %d entries", tier, len(scored))
        return index_path

    def rebuild_all_indexes(self, today: date | None = None) -> dict[str, Path]:
        """Rebuild _index.md for all tiers."""
        return {
            tier: self.rebuild_index(tier, today)
            for tier in ["stm", "ltm", "archive"]
        }

    def get_archive_candidates(self, today: date | None = None) -> list[ScoredFile]:
        """Find STM files that should be archived."""
        scored = self.score_tier("stm", today)
        return [s for s in scored if s.should_archive]

    def get_forget_candidates(self, today: date | None = None) -> list[ScoredFile]:
        """Find archive files that should be forgotten (deleted)."""
        scored = self.score_tier("archive", today)
        return [s for s in scored if s.should_forget]

    def get_stats(self, today: date | None = None) -> dict[str, Any]:
        """Get scoring statistics across all tiers."""
        all_scored = self.score_all(today)
        stats: dict[str, Any] = {}

        for tier, scored_list in all_scored.items():
            if not scored_list:
                stats[tier] = {"count": 0}
                continue
            scores = [s.score for s in scored_list]
            stats[tier] = {
                "count": len(scores),
                "highest": max(scores),
                "lowest": min(scores),
                "median": sorted(scores)[len(scores) // 2],
                "archive_candidates": sum(1 for s in scored_list if s.should_archive),
                "forget_candidates": sum(1 for s in scored_list if s.should_forget),
            }

        return stats

#!/usr/bin/env python3
"""
Standalone memory scoring + linking + index rebuild.

Replaces the dream pipeline's dependency on the legacy Python service
(src/memory/scorer.py, src/memory/linker.py). Same formula, same output
format, zero imports from src/ — only stdlib + PyYAML.

Formula: score = (base_weight * recency * reference_boost * urgency_boost) / 8.0
  recency         e^(-days_since_update / half_life); STM=30d, archive=180d,
                  LTM fixed at 0.99 (knowledge barely decays)
  reference_boost 1.0 + 0.1 * incoming_link_count
  urgency_boost   1.0 + 0.15 * (urgency - 1), urgency 1-5 from frontmatter

Pinning: a file with `score_frozen: true` in frontmatter keeps its stored
`score:` untouched by the formula (add a `note:` explaining why). Use for
files the formula mis-ranks (e.g. an archived reference that must stay hot).

Usage:
  python3 scripts/memory_scoring.py            # link + rescore + rebuild indexes
  python3 scripts/memory_scoring.py --stats    # print stats only, no writes
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None  # fall back to the minimal flat parser below

AGENT_ROOT = Path(__file__).resolve().parent.parent
TIER_DIRS = {
    "stm": AGENT_ROOT / "storage" / "short_term_memory",
    "ltm": AGENT_ROOT / "long-term-memory",
    "archive": AGENT_ROOT / "archive",
}
TIER_NAMES = {"stm": "Short-Term Memory", "ltm": "Long-Term Memory", "archive": "Archive"}

HALF_LIFE = {"stm": 30, "archive": 180}
LTM_FIXED_RECENCY = 0.99
NORMALIZATION = 8.0
URGENCY_BOOST_PER_LEVEL = 0.15
MIN_LINK_OVERLAP = 3

CATEGORY_KEYWORDS = {
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
    "pm_patterns": ["ticket", "routing", "pm", "kristine", "sprint", "jira"],
}


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith(("'", '"')) and raw.endswith(("'", '"')) and len(raw) >= 2:
        return raw[1:-1]
    if raw in ("", "null", "~"):
        return None
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass
    return raw


def _parse_flat_yaml(text: str) -> dict:
    """Minimal parser for the `key: value` + list frontmatter used in this repo.
    Only used when PyYAML is unavailable.

    Handles BOTH block lists (`tags:` then `- item`) and flow lists (`[a, b]`).
    Block-list support is load-bearing: without it `tags:` parsed to the empty
    string, which silently (a) blanked the Tags column in every _index.md,
    (b) starved auto-linking of its keywords, and (c) made write_frontmatter
    emit `tags:` with no items — destroying the tags of every file it rewrote.
    Tags are retrieval triggers, so that was silent memory loss (2026-08-15).
    Same defect class as the run-regression.py grader parser fixed the same day;
    when fixing a hand-rolled fallback parser, grep for its siblings."""
    meta: dict = {}
    list_key: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        # A block-list item belongs to the most recent bare `key:` line. Checked
        # before the ':' test — an item may itself contain a colon (e.g. a URL).
        if line.lstrip().startswith("- ") and list_key is not None:
            meta.setdefault(list_key, []).append(_parse_scalar(line.lstrip()[2:]))
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        list_key = None
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            meta[key] = [_parse_scalar(x) for x in inner.split(",")] if inner else []
        elif not raw:
            # Bare `key:` — a block list opens here, or it is genuinely empty.
            # Default to [] and let following `- ` items fill it.
            list_key = key
            meta[key] = []
        else:
            meta[key] = _parse_scalar(raw)
    return meta


def _dump_flat_yaml(meta: dict) -> str:
    lines = []
    for key, val in meta.items():
        if isinstance(val, list):
            # Block list — matches PyYAML's default_flow_style=False output, so
            # the with-/without-PyYAML paths round-trip to the same shape.
            lines.append(f"{key}:")
            lines.extend(f"- {v}" for v in val)
        elif isinstance(val, str) and (":" in val or "#" in val or val != val.strip()):
            escaped = val.replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
        else:
            lines.append(f"{key}: {val if val is not None else ''}")
    return "\n".join(lines)


def read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}
    try:
        end = content.index("\n---", 3)
    except ValueError:
        return {}
    block = content[4:end]
    if yaml is not None:
        try:
            return yaml.safe_load(block) or {}
        except yaml.YAMLError:
            return {}
    return _parse_flat_yaml(block)


def write_frontmatter(path: Path, meta: dict) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    if content.startswith("---\n"):
        end = content.index("\n---", 3)
        # end points at the newline BEFORE the closing '---', so end + 4 lands on the
        # newline that terminates the closing delimiter line. Leaving it in and then
        # writing '---\n' + body re-inserted one blank line on every single write, so
        # STM/LTM bodies grew a blank line per dream run (LBS-1541 reached 106).
        # Strip all leading blank lines and re-emit exactly one separator: idempotent.
        body = content[end + 4:].lstrip("\n")
    else:
        body = content.lstrip("\n")
    if yaml is not None:
        yaml_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()
    else:
        yaml_str = _dump_flat_yaml(meta)
    path.write_text(f"---\n{yaml_str}\n---\n\n{body}", encoding="utf-8")


def list_tier_files(tier: str) -> list[Path]:
    d = TIER_DIRS[tier]
    if not d.exists():
        return []
    return [f for f in sorted(d.glob("*.md")) if f.name != "_index.md"]


def to_date(val) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            return date.today()
    return date.today()


# ── Linking ──────────────────────────────────────────────────────


def extract_keywords(path: Path, meta: dict) -> set[str]:
    content = path.read_text(encoding="utf-8").lower()
    keywords = set()
    tags = meta.get("tags", [])
    if isinstance(tags, list):
        keywords.update(str(t).lower() for t in tags)
    for kw in CATEGORY_KEYWORDS.get(meta.get("category", ""), []):
        if kw in content:
            keywords.add(kw)
    return keywords


def auto_link_all() -> int:
    files = list_tier_files("stm") + list_tier_files("ltm")
    metas = {f: read_frontmatter(f) for f in files}
    ids = {f: metas[f].get("id", f.stem) for f in files}
    kws = {ids[f]: extract_keywords(f, metas[f]) for f in files}
    path_by_id = {ids[f]: f for f in files}

    added = 0
    sorted_ids = sorted(path_by_id)
    for i, a in enumerate(sorted_ids):
        for b in sorted_ids[i + 1:]:
            if len(kws[a] & kws[b]) < MIN_LINK_OVERLAP:
                continue
            for x, y in ((a, b), (b, a)):
                meta = metas[path_by_id[x]]
                links = meta.get("links") if isinstance(meta.get("links"), list) else []
                if y not in links:
                    meta["links"] = sorted(set(links + [y]))
                    write_frontmatter(path_by_id[x], meta)
                    added += 1
    return added


# ── Scoring ──────────────────────────────────────────────────────


def score_file(path: Path, meta: dict, incoming: int, today: date) -> tuple[float, int]:
    base_weight = float(meta.get("base_weight", 0.9))
    tier = meta.get("type", "stm")
    days_since = (today - to_date(meta.get("updated", today))).days

    if tier == "ltm":
        recency = LTM_FIXED_RECENCY
    else:
        recency = math.exp(-days_since / HALF_LIFE.get(tier, 30))

    boost = 1.0 + 0.1 * incoming
    try:
        urgency = max(1, min(5, int(meta.get("urgency", 1))))
    except (TypeError, ValueError):
        urgency = 1
    urgency_boost = 1.0 + URGENCY_BOOST_PER_LEVEL * (urgency - 1)

    return round((base_weight * recency * boost * urgency_boost) / NORMALIZATION, 4), days_since


def rescore_and_reindex(write: bool = True) -> dict:
    today = date.today()
    all_files = [(t, f) for t in TIER_DIRS for f in list_tier_files(t)]
    metas = {f: read_frontmatter(f) for _, f in all_files}

    incoming: dict[str, int] = {}
    for _, f in all_files:
        for link in metas[f].get("links", []) if isinstance(metas[f].get("links"), list) else []:
            incoming[link] = incoming.get(link, 0) + 1

    stats: dict = {}
    for tier in TIER_DIRS:
        scored = []
        for f in list_tier_files(tier):
            meta = metas[f]
            file_id = meta.get("id", f.stem)
            if str(meta.get("score_frozen", "")).lower() == "true":
                # Pinned against the formula (user/dream intent — e.g. an
                # archived reference the formula over-ranks). Keep the stored
                # score; set score_frozen: true + score: + note: in frontmatter.
                scored.append((float(meta.get("score", 0.0) or 0.0), file_id, meta))
                continue
            score, _ = score_file(f, meta, incoming.get(file_id, 0), today)
            if write and abs(float(meta.get("score", 0.0) or 0.0) - score) > 0.0001:
                meta["score"] = score
                write_frontmatter(f, meta)
            scored.append((score, file_id, meta))
        scored.sort(key=lambda s: s[0], reverse=True)

        if write:
            lines = [
                f"# {TIER_NAMES[tier]} Index",
                "",
                "> Auto-generated by scoring engine. Do not edit manually.",
                f"> Last updated: {today.isoformat()}",
                "",
            ]
            if tier == "archive":
                lines += ["| Score | ID | Summary | Original Tier | Archived |",
                          "|-------|-----|---------|---------------|----------|"]
                for score, file_id, meta in scored:
                    lines.append(f"| {score:.2f} | {file_id} | {meta.get('summary', '')} | "
                                 f"{meta.get('original_tier', 'stm')} | {meta.get('updated', '')} |")
            else:
                lines += ["| Score | ID | Summary | Tags | Status | Category | Updated |",
                          "|-------|-----|---------|------|--------|----------|---------|"]
                for score, file_id, meta in scored:
                    tags = meta.get("tags", [])
                    tag_str = " ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags or "")
                    lines.append(f"| {score:.2f} | {file_id} | {meta.get('summary', '')} | {tag_str} | "
                                 f"{meta.get('status', 'active')} | {meta.get('category', 'technical')} | "
                                 f"{meta.get('updated', '')} |")
            lines.append("")
            (TIER_DIRS[tier] / "_index.md").write_text("\n".join(lines), encoding="utf-8")

        scores = [s[0] for s in scored]
        stats[tier] = {
            "count": len(scores),
            "highest": max(scores) if scores else 0,
            "lowest": min(scores) if scores else 0,
            "median": sorted(scores)[len(scores) // 2] if scores else 0,
        }
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", action="store_true", help="print stats only, no writes")
    args = parser.parse_args()

    if args.stats:
        stats = rescore_and_reindex(write=False)
    else:
        added = auto_link_all()
        print(f"Auto-linked: {added} new link entries")
        stats = rescore_and_reindex(write=True)
        print("Scores and indexes rebuilt")

    for tier, s in stats.items():
        print(f"  {tier}: count={s['count']} highest={s['highest']:.2f} "
              f"lowest={s['lowest']:.2f} median={s['median']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

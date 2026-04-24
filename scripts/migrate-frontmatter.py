#!/usr/bin/env python3
"""
One-time migration: add YAML frontmatter to all memory files.

Targets:
  - knowledge/*.md      → type: ltm
  - storage/short_term_memory/*.md → type: stm

Safe to re-run: skips files that already have frontmatter.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent

# ── Knowledge file metadata (hand-mapped) ────────────────────────────

KNOWLEDGE_META = {
    "emr-integration.md": {
        "id": "emr-integration",
        "category": "emr_integration",
        "base_weight": 1.0,
        "summary": "EMR/HL7/SFTP integration rules, identity mapping, MSH values, bundle config",
        "tags": ["emr", "hl7", "integration", "provider", "practice"],
    },
    "patterns.md": {
        "id": "patterns",
        "category": "repo_patterns",
        "base_weight": 0.8,
        "summary": "Build/deploy patterns, investigation flows, DB connections, known issues",
        "tags": ["patterns", "build", "deploy", "investigation"],
    },
    "repos.md": {
        "id": "repos",
        "category": "technical",
        "base_weight": 0.9,
        "summary": "Active repo reference: tech stack, ports, key areas, setup",
        "tags": ["repos", "nestjs", "prisma", "grpc"],
    },
    "ticket-routing.md": {
        "id": "ticket-routing",
        "category": "pm_patterns",
        "base_weight": 0.7,
        "summary": "Ticket keyword to repo/module routing table",
        "tags": ["routing", "ticket", "pm"],
    },
}

# ── STM category inference ────────────────────────────────────────────

EMR_KEYWORDS = [
    "emr", "integration", "hl7", "ehr", "cerbo", "athena", "optimantra",
    "docvilla", "vendor", "practice id", "provider id", "sftp",
    "order_client", "ehr_integration", "msh", "bundle",
]

CALENDAR_KEYWORDS = [
    "calendar", "clinician", "appointment", "schedule", "timezone",
    "availability", "migration", "v2_calendar",
]


def infer_stm_category(content: str) -> tuple[str, float]:
    """Return (category, base_weight) based on STM content keywords."""
    lower = content.lower()
    emr_hits = sum(1 for kw in EMR_KEYWORDS if kw in lower)
    cal_hits = sum(1 for kw in CALENDAR_KEYWORDS if kw in lower)

    if emr_hits >= 2:
        return "emr_integration", 1.0
    if cal_hits >= 2:
        return "technical", 0.9
    return "technical", 0.9


def parse_stm_header(content: str) -> dict:
    """Extract status and created date from STM header lines."""
    status = "active"
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    m = re.search(r">\s*Status:\s*(\w+)", content)
    if m:
        status = m.group(1).strip()

    m = re.search(r">\s*Created:\s*([\d-]+)", content)
    if m:
        created = m.group(1).strip()

    return {"status": status, "created": created}


def has_frontmatter(content: str) -> bool:
    """Check if file already has YAML frontmatter."""
    return content.startswith("---\n")


def build_frontmatter(meta: dict) -> str:
    """Build YAML frontmatter string from metadata dict."""
    links = meta.get("links", [])
    tags = meta.get("tags", [])
    lines = [
        "---",
        f"id: {meta['id']}",
        f"type: {meta['type']}",
        f"category: {meta['category']}",
        f"status: {meta['status']}",
        f"score: 0.00",
        f"base_weight: {meta['base_weight']}",
        f"created: {meta['created']}",
        f"updated: {meta['updated']}",
        f"links: [{', '.join(links)}]",
        f"tags: [{', '.join(tags)}]",
        f"summary: \"{meta['summary']}\"",
        "---",
        "",
    ]
    return "\n".join(lines)


def migrate_knowledge_files() -> int:
    """Add frontmatter to knowledge/*.md files."""
    knowledge_dir = AGENT_ROOT / "knowledge"
    if not knowledge_dir.exists():
        print("  [SKIP] knowledge/ directory not found")
        return 0

    count = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for md_file in sorted(knowledge_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")

        if has_frontmatter(content):
            print(f"  [SKIP] {md_file.name} — already has frontmatter")
            continue

        meta_override = KNOWLEDGE_META.get(md_file.name)
        if not meta_override:
            print(f"  [SKIP] {md_file.name} — no metadata mapping defined")
            continue

        meta = {
            "id": meta_override["id"],
            "type": "ltm",
            "category": meta_override["category"],
            "status": "active",
            "base_weight": meta_override["base_weight"],
            "created": today,
            "updated": today,
            "links": [],
            "tags": meta_override.get("tags", []),
            "summary": meta_override.get("summary", md_file.stem),
        }

        frontmatter = build_frontmatter(meta)
        md_file.write_text(frontmatter + content, encoding="utf-8")
        print(f"  [OK]   {md_file.name} — category={meta['category']}, weight={meta['base_weight']}")
        count += 1

    return count


def migrate_stm_files() -> int:
    """Add frontmatter to storage/short_term_memory/*.md files."""
    stm_dir = AGENT_ROOT / "storage" / "short_term_memory"
    if not stm_dir.exists():
        print("  [SKIP] storage/short_term_memory/ directory not found")
        return 0

    count = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for md_file in sorted(stm_dir.glob("*.md")):
        if md_file.name == "_index.md":
            continue

        content = md_file.read_text(encoding="utf-8")

        if has_frontmatter(content):
            print(f"  [SKIP] {md_file.name} — already has frontmatter")
            continue

        ticket_id = md_file.stem
        header = parse_stm_header(content)
        category, base_weight = infer_stm_category(content)

        first_line = ""
        for line in content.split("\n"):
            if line.startswith("**") or ("Ticket" in line and "-" in line):
                first_line = line.strip("*# \n")
                break

        summary = first_line[:100] if first_line else f"Work loop record for {ticket_id}"

        meta = {
            "id": ticket_id,
            "type": "stm",
            "category": category,
            "status": header["status"],
            "base_weight": base_weight,
            "created": header["created"],
            "updated": today,
            "links": [],
            "tags": [ticket_id.lower()],
            "summary": summary,
        }

        frontmatter = build_frontmatter(meta)
        md_file.write_text(frontmatter + content, encoding="utf-8")
        print(f"  [OK]   {md_file.name} — category={category}, status={header['status']}")
        count += 1

    return count


def main():
    print("=== Phase 0: YAML Frontmatter Migration ===\n")

    print("1. Migrating knowledge/*.md files...")
    k_count = migrate_knowledge_files()
    print(f"   → {k_count} files migrated\n")

    print("2. Migrating storage/short_term_memory/*.md files...")
    s_count = migrate_stm_files()
    print(f"   → {s_count} files migrated\n")

    total = k_count + s_count
    print(f"=== Done: {total} files migrated ===")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

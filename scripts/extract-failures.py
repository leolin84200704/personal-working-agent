#!/usr/bin/env python3
"""
Extract the `## Failures` section from every STM file and consolidate them
into `long-term-memory/failures.md` — a single index keyed by root-cause theme.

Designed to run as part of the dream pipeline (idempotent) and on-demand.
The prose is regenerated each run; do not edit the entries by hand.

Regeneration is NOT a clean overwrite, because the file outlives its sources:

  - `score` and part of `links` are maintained by memory_scoring.py's auto-linker,
    not derivable from STM. Rewriting them from scratch discarded 49 of 90 links
    on 2026-08-18 (and 129 lines of them on 2026-07-29).
  - an entry whose STM has been archived has no source left to re-render, so a
    from-scratch pass silently deletes it. VP-16720 existed in no STM and no
    journal — only here — and vanished exactly that way.

So: frontmatter that this script does not own is carried over, links are unioned,
and an entry the current scan cannot produce is carried over from the file itself
rather than dropped. Refusing to write would have been worse than useless here —
an orphaned entry stays orphaned, so every later run would refuse too, and the
only way out would be --prune, which deletes exactly what the check was protecting.

Usage:
  python3 scripts/extract-failures.py            # write LTM file
  python3 scripts/extract-failures.py --print    # print to stdout only
  python3 scripts/extract-failures.py --prune    # drop entries whose STM is gone, do not carry them
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STM_DIR = ROOT / "storage" / "short_term_memory"
LTM_OUT = ROOT / "long-term-memory" / "failures.md"

# Heuristic theme classifier: first match wins.
# Order matters — most specific themes first.
THEMES: list[tuple[str, str, re.Pattern]] = [
    ("build-tooling",       "Build / TypeScript / Tooling",
     re.compile(r"tsc|rootDir|dist[ /]|nest build|webpack|tsconfig|prisma generate|postbuild", re.I)),
    ("deploy-coordination", "Deploy / commit / push coordination",
     re.compile(r"\bdeploy\b|不用 build|現在不用|該不該|commit ↔|push 沒先|build 嗎|該 deploy|是否需要 deploy", re.I)),
    ("prod-side-effects",   "Production side-effects (Kafka / email / SFTP)",
     re.compile(r"prod\b|production|kafka|email send|SFTP|fire-and-forget|HL7 sent|垃圾 HL7", re.I)),
    ("db-migration",        "DB / migration / backfill",
     re.compile(r"migration|backfill|schema\b|psql|prisma migrate|calendar_dev|dirty data|INSERT|duplicate|constraint|transaction.*rollback|customer_id|clinic_id|column", re.I)),
    ("scope-communication", "Scope / requirement / PM communication",
     re.compile(r"scope|誤解|否定句|implicit|過去 event|expand|擴大|PM (確認|溝通)|requirement|assumption|first.pass|schema change|YAML|pattern detection|wrong pattern", re.I)),
    ("error-handling",      "Error handling / throw vs log",
     re.compile(r"throw new Error|try.catch|catch|error.message|報錯|沒新 data 不報錯|silent", re.I)),
    ("tool-usage",          "Tool / cwd / branch / repo confusion",
     re.compile(r"cwd|persistence|wrong repo|wrong branch|cross-repo|git switch|git checkout.*wrong", re.I)),
    ("auth-permission",     "Auth / permission / role",
     re.compile(r"role|permission|admin|clinic user|Forbidden|gate|isClinic|isAdmin", re.I)),
    ("redis-cache",         "Redis / cache / pending list",
     re.compile(r"redis|SREM|SADD|pending|cache|ghost|race", re.I)),
    ("grpc-network",        "gRPC / network / timeout",
     re.compile(r"gRPC|grpc|getaddrinfo|ENOTFOUND|timeout|deadline|UNAVAILABLE", re.I)),
    ("bullmq-queue",        "BullMQ / queue / worker",
     re.compile(r"BullMQ|bullmq|queue|worker|concurrency|Promise\.race", re.I)),
    ("test-mocking",        "Test / mock / spec",
     re.compile(r"jest|mock|spec\.ts|integration test|e2e", re.I)),
    ("graphql-api",         "GraphQL / API design",
     re.compile(r"GraphQL|graphql|resolver|@Args|@Mutation|@Query", re.I)),
]
DEFAULT_THEME = ("other", "Other / uncategorized")

# Body content is treated as empty/placeholder if it matches any of these.
PLACEHOLDER_RE = re.compile(
    r"^\s*(?:[（(]?\s*(?:無|none|N/A|pending|尚未 execute|尚未執行)\s*[)）]?|_+\s*\([^)]+\)\s*_+)\s*$",
    re.I,
)
MIN_ENTRY_BODY_LEN = 20  # below this we treat as not-an-entry

FAILURES_RE = re.compile(
    r"^##\s+Failures\s*$\n(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)
SUB_ENTRY_RE = re.compile(
    r"###\s+(?:\[(?P<date>[\d\- :]+)\]\s+)?(?P<title>.+?)\s*$", re.MULTILINE
)


def extract_section(text: str) -> str | None:
    m = FAILURES_RE.search(text)
    if not m:
        return None
    body = m.group(1).strip()
    if not body or re.fullmatch(r"[（(]\s*(無|none|N/A|pending)\s*[)）]", body, re.I):
        return None
    return body


def classify(text: str) -> tuple[str, str]:
    for key, label, pat in THEMES:
        if pat.search(text):
            return key, label
    return DEFAULT_THEME


def split_entries(body: str) -> list[tuple[str, str, str]]:
    """
    Split a failures section into individual entries.
    Returns [(date, title, body), ...] — falls back to a single ('', '', body)
    if no ### sub-headers exist.
    """
    headers = list(SUB_ENTRY_RE.finditer(body))
    if not headers:
        return [("", "", body.strip())]
    entries = []
    for i, h in enumerate(headers):
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        chunk = body[start:end].strip()
        entries.append((h.group("date") or "", h.group("title").strip(), chunk))
    return entries


def _is_placeholder_entry(title: str, body: str) -> bool:
    """Treat as placeholder if there's no meaningful content."""
    body_stripped = body.strip()
    if not body_stripped and not title.strip():
        return True
    # Body is empty or just a placeholder marker
    if not body_stripped or PLACEHOLDER_RE.match(body_stripped):
        # …and there's no informative title either
        if not title.strip() or PLACEHOLDER_RE.match(title.strip()):
            return True
        # Title exists but body is empty/placeholder and the title is too short
        if len(title.strip()) < MIN_ENTRY_BODY_LEN:
            return True
    return False


def gather() -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    if not STM_DIR.exists():
        return grouped
    for stm in sorted(STM_DIR.glob("*.md")):
        if stm.name.startswith("_"):
            continue
        text = stm.read_text(encoding="utf-8")
        body = extract_section(text)
        if not body:
            continue
        ticket = stm.stem
        for entry_date, title, entry_body in split_entries(body):
            if _is_placeholder_entry(title, entry_body):
                continue
            key = classify(f"{title}\n{entry_body}")
            grouped[key].append({
                "ticket": ticket,
                "date": entry_date.strip(),
                "title": title,
                "body": entry_body,
            })
    return grouped


ENTRY_ID_RE = re.compile(r"^### \*\*\[\[([^\]]+)\]\]", re.M)


def read_existing(path: Path) -> dict:
    """What the file on disk already holds and this script cannot re-derive."""
    if not path.exists():
        return {"created": None, "score": None, "links": [], "entry_ids": set()}
    text = path.read_text(encoding="utf-8")
    created = score = None
    links: list[str] = []
    in_links = False
    for line in text.splitlines():
        if line.startswith("---") and links:
            break
        if line.startswith("created:"):
            created = line.split(":", 1)[1].strip()
        elif line.startswith("score:"):
            score = line.split(":", 1)[1].strip()
        elif line.startswith("links:"):
            in_links = True
        elif in_links:
            if line.startswith("- "):
                links.append(line[2:].strip())
            elif re.match(r"^[a-z_]+:", line):
                in_links = False
    return {
        "created": created,
        "score": score,
        "links": links,
        "entry_ids": set(ENTRY_ID_RE.findall(text)),
    }


SECTION_RE = re.compile(r"^## (?P<label>.+?) <a id='(?P<key>[^']+)'></a>\s*$", re.M)


def orphan_entries(path: Path, produced_ids: set[str]) -> dict[tuple[str, str], list[dict]]:
    """Entries in the file on disk that this run cannot re-render.

    Their STM has been archived, so the scan no longer sees them, but the file may
    be the only place the knowledge still exists. Parsed back out of the previous
    render and returned in the same shape as gather(), so they flow through the
    normal rendering path and the counts and ToC stay honest.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    sections = [(m.start(), m.group("key"), m.group("label")) for m in SECTION_RE.finditer(text)]
    if not sections:
        return {}

    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    heads = list(re.finditer(r"^### \*\*\[\[([^\]]+)\]\]\s*(.*)$", text, re.M))
    for i, m in enumerate(heads):
        ticket = m.group(1)
        if ticket in produced_ids:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        nxt = SECTION_RE.search(text, m.end())
        if nxt and nxt.start() < end:
            end = nxt.start()
        body = text[m.end():end].strip()
        body = re.sub(r"\n-{3,}\s*$", "", body).strip()

        rest = m.group(2)
        entry_date = title = ""
        bits = [b.strip() for b in rest.split("—")]
        for b in bits:
            if not b:
                continue
            if b.startswith("`") and b.endswith("`") and not entry_date:
                entry_date = b.strip("`")
            elif not title:
                title = b

        key, label = sections[0][1], sections[0][2]
        for pos, k, lab in sections:
            if pos < m.start():
                key, label = k, lab
            else:
                break
        out[(key, label)].append(
            {"ticket": ticket, "date": entry_date, "title": title, "body": body}
        )
    return dict(out)


def render(grouped: dict[tuple[str, str], list[dict]], prior: dict | None = None) -> str:
    prior = prior or {"created": None, "score": None, "links": []}
    today = date.today().isoformat()
    total = sum(len(v) for v in grouped.values())

    # Collect outbound links: every ticket that contributed an entry, plus
    # any [[xxx]] reference inside an entry body. Ordered, deduped.
    seen: set[str] = set()
    ordered_links: list[str] = []
    body_link_re = re.compile(r"\[\[([\w\-]+)\]\]")
    for entries in grouped.values():
        for e in entries:
            for tid in [e["ticket"], *body_link_re.findall(e["body"])]:
                if tid and tid not in seen and tid != "failures":
                    seen.add(tid)
                    ordered_links.append(tid)

    # Union with what is already there: the auto-linker in memory_scoring.py adds
    # links this script has no way to rediscover (incident ids, routing files,
    # cross-instance feedback keys). Rebuilding from STM alone throws them away.
    for tid in prior.get("links") or []:
        if tid and tid not in seen and tid != "failures":
            seen.add(tid)
            ordered_links.append(tid)
    ordered_links.sort()

    links_yaml = "\n".join(f"- {tid}" for tid in ordered_links) if ordered_links else ""

    out = [
        "---",
        "id: failures",
        "type: ltm",
        "category: technical",
        "status: active",
        # score is memory_scoring.py's to compute; created is the file's real
        # birthday. Neither is ours to reset on every run.
        f"score: {prior.get('score') or '0.0'}",
        "base_weight: 0.9",
        "urgency: 3",
        f"created: {prior.get('created') or today}",
        f"updated: {today}",
        "links:" if ordered_links else "links: []",
    ]
    if ordered_links:
        out.append(links_yaml)
    out += [
        "tags:",
        "- failures",
        "- root-cause",
        "- auto-generated",
        f'summary: Auto-aggregated failure index from {total} entries across STM',
        "---",
        "",
        "# Failure Index",
        "",
        "> 自動生成自 `storage/short_term_memory/*.md` 的 `## Failures` 區段。",
        "> 由 `scripts/extract-failures.py` 維護，手動編輯會被下次 run 覆蓋。",
        f"> Last updated: {today} — total {total} entries",
        "",
        "## Themes",
        "",
    ]
    # ToC
    for (key, label), entries in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        out.append(f"- [{label}](#{key}) — {len(entries)} entries")
    out.append("")
    out.append("---")
    out.append("")

    # Sections
    for (key, label), entries in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        out.append(f"## {label} <a id='{key}'></a>")
        out.append("")
        for e in entries:
            header_bits = [f"**[[{e['ticket']}]]**"]
            if e["date"]:
                header_bits.append(f"`{e['date']}`")
            if e["title"]:
                header_bits.append(e["title"])
            out.append("### " + " — ".join(header_bits))
            out.append("")
            out.append(e["body"])
            out.append("")
        out.append("---")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print to stdout, do not write file")
    ap.add_argument("--prune", action="store_true",
                    help="write even if entries would be dropped (their STM is gone)")
    args = ap.parse_args()

    prior = read_existing(LTM_OUT)
    grouped = gather()

    produced = {e["ticket"] for entries in grouped.values() for e in entries}
    carried = orphan_entries(LTM_OUT, produced) if not args.prune else {}
    carried_ids = sorted(e["ticket"] for entries in carried.values() for e in entries)
    for key, entries in carried.items():
        grouped.setdefault(key, []).extend(entries)

    rendered = render(grouped, prior)
    dropped = sorted(prior["entry_ids"] - set(ENTRY_ID_RE.findall(rendered)))

    if args.print:
        if dropped:
            print(f"WARNING: dropping {len(dropped)} entries: {', '.join(dropped)}", file=sys.stderr)
        sys.stdout.write(rendered)
        return 0

    # Belt and braces: carrying orphans should make this unreachable without
    # --prune. If it ever fires, something else is eating entries — stop.
    if dropped and not args.prune:
        print(
            f"REFUSED to write {LTM_OUT.relative_to(ROOT)}: {len(dropped)} entries would be "
            f"lost even after carrying orphans forward: {', '.join(dropped)}",
            file=sys.stderr,
        )
        return 2

    LTM_OUT.parent.mkdir(exist_ok=True)
    LTM_OUT.write_text(rendered, encoding="utf-8")
    total = sum(len(v) for v in grouped.values())
    print(f"Wrote {LTM_OUT.relative_to(ROOT)} — {total} entries across {len(grouped)} themes")
    if carried_ids:
        print(f"  (carried {len(carried_ids)} entries whose STM is gone: {', '.join(carried_ids)})")
    if dropped:
        print(f"  (--prune: dropped {len(dropped)} entries: {', '.join(dropped)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

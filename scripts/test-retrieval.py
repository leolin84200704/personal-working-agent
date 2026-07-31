#!/usr/bin/env python3
"""
External-style retrieval quality test for lis-code-agent.

Ground truth: each STM file's `summary:` frontmatter line is treated as a
query that should retrieve the STM file itself (top-1).

Retrievers tested:
  1. grep — naive grep over markdown body for the query terms
  2. ripgrep weighted — multi-term ranked count of matches per file
  3. skill_index — lis-code-agent's keyword-weighted skill matcher
                   (extended to STM by re-pointing tier_dir)

Metrics per retriever:
  hit@1, hit@3, hit@5, mean reciprocal rank (MRR), zero-recall %

Why STM-as-query: simple, intrinsic, no external annotation. Bias caveat —
summary lines often share lexical tokens with the body (tag/id strings),
which favors grep-class retrievers. Compensate by tokenising aggressively
(drop ticket id, drop bracket prefixes) and reporting both raw and stripped.

Usage:
  python3 scripts/test-retrieval.py                 # run all retrievers
  python3 scripts/test-retrieval.py --label r1      # also save JSON snapshot
  python3 scripts/test-retrieval.py --diff baseline # compare with prior snapshot
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STM_DIR = ROOT / "storage" / "short_term_memory"
EVAL_OUT = ROOT / "eval-output"
EVAL_OUT.mkdir(exist_ok=True)

TICKET_PREFIX_RE = re.compile(r"^(?:VP-\d+|INCIDENT-\d+|LBS-\d+|PO-\d+|HL7-\w+)\s*[-—:]\s*", re.I)
STOPWORDS = {
    "the", "a", "an", "to", "in", "of", "for", "is", "and", "or", "with", "on",
    "by", "as", "at", "be", "from", "this", "that", "after", "before",
    "請", "用", "改", "把", "從", "做", "看", "跟", "都", "等", "有", "沒",
}


def load_stm() -> list[tuple[str, str, str]]:
    """Return [(id, summary, body), ...]"""
    items = []
    for f in sorted(STM_DIR.glob("*.md")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^summary:\s*(.+?)(?:\n[a-z_]+:|\n---)", text, re.MULTILINE | re.DOTALL)
        if not m:
            continue
        summary = re.sub(r"\s+", " ", m.group(1)).strip().strip("'\"")
        items.append((f.stem, summary, text))
    return items


def strip_query(q: str, file_id: str) -> str:
    """Make query 'fair' — remove ticket id and ticket-id prefix patterns."""
    q = TICKET_PREFIX_RE.sub("", q)
    q = q.replace(file_id, "")
    return q.strip()


def tokens(q: str) -> list[str]:
    raw = re.findall(r"[\w\-]+", q.lower())
    return [t for t in raw if len(t) > 2 and t not in STOPWORDS]


# --- Retrievers ---

def retrieve_grep(query: str, corpus: list[tuple[str, str, str]], file_id: str) -> list[str]:
    q = strip_query(query, file_id)
    if not q:
        return []
    terms = tokens(q)
    if not terms:
        return []
    scored = []
    for sid, _, body in corpus:
        score = sum(body.lower().count(t) for t in terms)
        if score > 0:
            scored.append((score, sid))
    scored.sort(reverse=True)
    return [sid for _, sid in scored]


def retrieve_summary_only(query: str, corpus: list[tuple[str, str, str]], file_id: str) -> list[str]:
    """Look only at frontmatter summaries (a higher-precision baseline)."""
    q = strip_query(query, file_id)
    terms = tokens(q)
    if not terms:
        return []
    scored = []
    for sid, summary, _ in corpus:
        score = sum(summary.lower().count(t) for t in terms)
        if score > 0:
            scored.append((score, sid))
    scored.sort(reverse=True)
    return [sid for _, sid in scored]


def retrieve_skill_index(query: str) -> list[str]:
    try:
        from src.memory.skill_index import SkillIndex  # type: ignore

        idx = SkillIndex()
        hits = idx.find_relevant(query, top_k=10)
        return [h.get("name", "") for h in hits]
    except Exception:
        return []


# --- Metrics ---

def hits_at_k(ranked: list[str], target: str, k: int) -> int:
    return int(target in ranked[:k])


def reciprocal_rank(ranked: list[str], target: str) -> float:
    for i, sid in enumerate(ranked, 1):
        if sid == target:
            return 1.0 / i
    return 0.0


def evaluate(name: str, retriever, corpus: list[tuple[str, str, str]], use_corpus: bool) -> dict:
    h1 = h3 = h5 = 0
    rrs = []
    zero = 0
    elapsed = 0.0
    for sid, summary, _ in corpus:
        t0 = time.perf_counter()
        if use_corpus:
            ranked = retriever(summary, corpus, sid)
        else:
            ranked = retriever(summary)
        elapsed += time.perf_counter() - t0
        if not ranked:
            zero += 1
        h1 += hits_at_k(ranked, sid, 1)
        h3 += hits_at_k(ranked, sid, 3)
        h5 += hits_at_k(ranked, sid, 5)
        rrs.append(reciprocal_rank(ranked, sid))
    n = max(len(corpus), 1)
    return {
        "retriever": name,
        "n": len(corpus),
        "hit@1": round(h1 / n, 3),
        "hit@3": round(h3 / n, 3),
        "hit@5": round(h5 / n, 3),
        "mrr": round(statistics.mean(rrs), 3),
        "zero_recall_pct": round(100 * zero / n, 1),
        "avg_ms": round(1000 * elapsed / n, 2),
    }


def run() -> dict:
    corpus = load_stm()
    if not corpus:
        return {"error": "no STM corpus"}

    results = []
    results.append(evaluate("grep_body", retrieve_grep, corpus, use_corpus=True))
    results.append(evaluate("summary_only", retrieve_summary_only, corpus, use_corpus=True))
    results.append(evaluate("skill_index", retrieve_skill_index, corpus, use_corpus=False))

    return {
        "corpus_size": len(corpus),
        "retrievers": results,
    }


def print_report(r: dict) -> None:
    if r.get("error"):
        print(r["error"])
        return
    print(f"# Retrieval Quality Test — corpus={r['corpus_size']} STM files")
    print()
    print(f"{'Retriever':<18} {'hit@1':>7} {'hit@3':>7} {'hit@5':>7} {'MRR':>7} {'zero%':>7} {'avg ms':>8}")
    print("-" * 65)
    for row in r["retrievers"]:
        print(
            f"{row['retriever']:<18} "
            f"{row['hit@1']:>7.3f} {row['hit@3']:>7.3f} {row['hit@5']:>7.3f} "
            f"{row['mrr']:>7.3f} {row['zero_recall_pct']:>6.1f}% {row['avg_ms']:>8.2f}"
        )


def diff(curr: dict, baseline: dict) -> list[str]:
    lines = []
    cb = {r["retriever"]: r for r in curr.get("retrievers", [])}
    bb = {r["retriever"]: r for r in baseline.get("retrievers", [])}
    for name in sorted(set(cb) | set(bb)):
        a = bb.get(name, {})
        b = cb.get(name, {})
        for k in ("hit@1", "hit@3", "hit@5", "mrr", "zero_recall_pct"):
            if k not in a or k not in b:
                continue
            if a[k] == b[k]:
                continue
            delta = round(b[k] - a[k], 3)
            sign = "+" if delta >= 0 else ""
            lines.append(f"  {name}.{k}: {a[k]} -> {b[k]} ({sign}{delta})")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label")
    ap.add_argument("--diff")
    args = ap.parse_args()

    today = time.strftime("%Y-%m-%d")
    r = run()
    print_report(r)

    if args.label:
        out = EVAL_OUT / f"{today}-retrieval-{args.label}.json"
        out.write_text(json.dumps(r, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\n→ Saved snapshot: {out}")

    if args.diff:
        target = Path(args.diff)
        if not target.exists():
            matches = sorted(EVAL_OUT.glob(f"*-retrieval-{args.diff}.json"))
            if not matches:
                print(f"\n[diff] No retrieval snapshot found matching '{args.diff}'", file=sys.stderr)
                sys.exit(2)
            target = matches[-1]
        baseline = json.loads(target.read_text(encoding="utf-8"))
        print(f"\n## Diff vs {target.name}")
        lines = diff(r, baseline)
        if not lines:
            print("- (no changes)")
        else:
            for line in lines:
                print(line)


if __name__ == "__main__":
    main()

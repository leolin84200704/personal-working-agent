"""Compare two LoCoMo benchmark result JSONs and emit a markdown report.

Usage:
    python -m benchmarks.harness.compare v0_<ts>.json v1_<ts>.json
    python -m benchmarks.harness.compare v0.json v1.json --output diff.md

The report contains:
- overall metric deltas (v1 - v0)
- per-category F1 / BLEU-1 / ROUGE-L table
- wins / losses / ties breakdown (at question level, keyed by
  ``sample_id + question``)
- token efficiency comparison (sum of prompt + completion tokens)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_records(payload: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in payload.get("records", []):
        key = (str(r.get("sample_id")), str(r.get("question")))
        idx[key] = r
    return idx


def _fmt_delta(v0: float, v1: float) -> str:
    delta = v1 - v0
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.4f}"


def _per_category_rows(v0_payload: Dict[str, Any], v1_payload: Dict[str, Any]) -> List[List[str]]:
    v0_cats = v0_payload.get("aggregate", {}).get("by_category", {})
    v1_cats = v1_payload.get("aggregate", {}).get("by_category", {})
    all_cats = sorted(set(v0_cats) | set(v1_cats))

    rows: List[List[str]] = []
    for cat in all_cats:
        a = v0_cats.get(cat, {"n": 0, "f1": 0.0, "bleu1": 0.0, "rougeL": 0.0})
        b = v1_cats.get(cat, {"n": 0, "f1": 0.0, "bleu1": 0.0, "rougeL": 0.0})
        rows.append([
            cat,
            str(a["n"]),
            f"{a['f1']:.3f}",
            f"{b['f1']:.3f}",
            _fmt_delta(a["f1"], b["f1"]),
            f"{a['bleu1']:.3f}",
            f"{b['bleu1']:.3f}",
            _fmt_delta(a["bleu1"], b["bleu1"]),
            f"{a['rougeL']:.3f}",
            f"{b['rougeL']:.3f}",
            _fmt_delta(a["rougeL"], b["rougeL"]),
        ])
    return rows


def _wins_losses(
    v0_records: Dict[Tuple[str, str], Dict[str, Any]],
    v1_records: Dict[Tuple[str, str], Dict[str, Any]],
    metric: str = "f1",
    epsilon: float = 1e-4,
) -> Dict[str, int]:
    wins = losses = ties = only_v0 = only_v1 = 0
    for key in set(v0_records) | set(v1_records):
        a = v0_records.get(key)
        b = v1_records.get(key)
        if a is None:
            only_v1 += 1
            continue
        if b is None:
            only_v0 += 1
            continue
        av = a["scores"].get(metric, 0.0)
        bv = b["scores"].get(metric, 0.0)
        if bv - av > epsilon:
            wins += 1
        elif av - bv > epsilon:
            losses += 1
        else:
            ties += 1
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "only_in_v0": only_v0,
        "only_in_v1": only_v1,
    }


def _total_tokens(records: List[Dict[str, Any]]) -> int:
    return sum(
        int(r.get("tokens", {}).get("prompt", 0))
        + int(r.get("tokens", {}).get("completion", 0))
        for r in records
    )


def _total_elapsed(records: List[Dict[str, Any]]) -> int:
    return sum(int(r.get("elapsed_ms", 0)) for r in records)


def render_markdown(v0_payload: Dict[str, Any], v1_payload: Dict[str, Any]) -> str:
    v0_meta = v0_payload.get("meta", {})
    v1_meta = v1_payload.get("meta", {})
    v0_agg = v0_payload.get("aggregate", {}).get("overall", {})
    v1_agg = v1_payload.get("aggregate", {}).get("overall", {})

    v0_records = _index_records(v0_payload)
    v1_records = _index_records(v1_payload)

    f1_wl = _wins_losses(v0_records, v1_records, "f1")
    rouge_wl = _wins_losses(v0_records, v1_records, "rougeL")

    v0_tokens = _total_tokens(v0_payload.get("records", []))
    v1_tokens = _total_tokens(v1_payload.get("records", []))
    v0_elapsed = _total_elapsed(v0_payload.get("records", []))
    v1_elapsed = _total_elapsed(v1_payload.get("records", []))

    lines: List[str] = []
    lines.append("# LoCoMo Benchmark Diff")
    lines.append("")
    lines.append(f"- **v0**: `{v0_meta.get('config_name', '?')}` "
                 f"(n={v0_meta.get('n_questions', 0)}, finished={v0_meta.get('finished_at', '?')})")
    lines.append(f"- **v1**: `{v1_meta.get('config_name', '?')}` "
                 f"(n={v1_meta.get('n_questions', 0)}, finished={v1_meta.get('finished_at', '?')})")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append("| Metric | v0 | v1 | Δ |")
    lines.append("|---|---|---|---|")
    for m in ("f1", "bleu1", "rougeL"):
        a = v0_agg.get(m, 0.0)
        b = v1_agg.get(m, 0.0)
        lines.append(f"| {m} | {a:.3f} | {b:.3f} | {_fmt_delta(a, b)} |")
    lines.append("")

    lines.append("## Per category")
    lines.append("")
    lines.append("| Category | n(v0) | F1 v0 | F1 v1 | ΔF1 | BLEU1 v0 | BLEU1 v1 | ΔBLEU1 | ROUGE-L v0 | ROUGE-L v1 | ΔROUGE-L |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in _per_category_rows(v0_payload, v1_payload):
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## Question-level wins / losses (F1)")
    lines.append("")
    lines.append(f"- Wins (v1 > v0): **{f1_wl['wins']}**")
    lines.append(f"- Losses (v1 < v0): **{f1_wl['losses']}**")
    lines.append(f"- Ties: {f1_wl['ties']}")
    if f1_wl["only_in_v0"] or f1_wl["only_in_v1"]:
        lines.append(f"- Only in v0: {f1_wl['only_in_v0']} · Only in v1: {f1_wl['only_in_v1']}")
    lines.append("")

    lines.append("## Question-level wins / losses (ROUGE-L)")
    lines.append("")
    lines.append(f"- Wins: **{rouge_wl['wins']}** · Losses: **{rouge_wl['losses']}** · Ties: {rouge_wl['ties']}")
    lines.append("")

    lines.append("## Token & latency efficiency")
    lines.append("")
    lines.append("| Axis | v0 | v1 | Δ |")
    lines.append("|---|---|---|---|")
    lines.append(f"| total tokens | {v0_tokens} | {v1_tokens} | {v1_tokens - v0_tokens:+d} |")
    lines.append(f"| total elapsed ms | {v0_elapsed} | {v1_elapsed} | {v1_elapsed - v0_elapsed:+d} |")
    lines.append("")

    lines.append("> Generated by `benchmarks.harness.compare`.")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("v0", type=Path, help="Baseline result JSON.")
    parser.add_argument("v1", type=Path, help="New-version result JSON.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the markdown diff (default: stdout).",
    )
    args = parser.parse_args(argv)

    v0_payload = _load(args.v0)
    v1_payload = _load(args.v1)
    md = render_markdown(v0_payload, v1_payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.write(md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

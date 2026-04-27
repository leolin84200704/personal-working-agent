"""Re-judge an existing benchmark result JSON using the LLM judge.

Reads a result JSON produced by ``benchmarks.harness.runner`` and runs
the LLM judge (via ``claude -p``) over each record. Writes an augmented
JSON with the same shape plus ``llm_judge_score`` / ``llm_judge_raw``
on every record, and an updated ``aggregate`` block that includes the
LLM-judge means and correctness percentages.

Usage::

    python -m benchmarks.harness.re_judge \
        --input benchmarks/results/checkpoint_A_qa20.json \
        --output benchmarks/results/rejudge_A_qa20.json \
        --model claude-sonnet-4-6

Why: string-overlap metrics (F1/BLEU/ROUGE-L) penalise verbose answers
even when they're factually correct. The LLM judge gives a verdict-level
correctness signal that's invariant to phrasing length.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow ``python -m benchmarks.harness.re_judge`` from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.harness.judge import Judge, aggregate


def re_judge(
    input_path: Path,
    output_path: Path,
    model: str = "claude-sonnet-4-6",
    timeout: int = 30,
    limit: Optional[int] = None,
    progress_every: int = 10,
) -> Dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records: List[Dict[str, Any]] = list(payload.get("records") or [])
    if limit is not None:
        records = records[:limit]

    judge = Judge(
        llm_judge_enabled=True,
        llm_judge_model=model,
        llm_judge_timeout=timeout,
    )

    started_at = datetime.now(timezone.utc).isoformat()
    t_start = time.perf_counter()

    new_records: List[Dict[str, Any]] = []
    for i, rec in enumerate(records, 1):
        question = rec.get("question", "")
        expected = rec.get("expected_answer", "")
        actual = rec.get("agent_answer", "")
        category = rec.get("category", "unknown")

        verdict = judge._llm_judge(question, expected, actual, category)

        # Preserve everything from the original record, then layer the
        # LLM judge fields onto its scores dict.
        new_rec = dict(rec)
        scores = dict(rec.get("scores") or {})
        scores["llm_judge"] = verdict
        scores["llm_judge_score"] = verdict.get("score")
        scores["llm_judge_raw"] = (verdict.get("raw") or "")[:200]
        new_rec["scores"] = scores
        new_records.append(new_rec)

        if progress_every and i % progress_every == 0:
            elapsed = time.perf_counter() - t_start
            rate = i / elapsed if elapsed > 0 else 0.0
            print(
                f"  [{i}/{len(records)}] "
                f"calls={judge.llm_judge_calls} fails={judge.llm_judge_failures} "
                f"rate={rate:.2f}/s",
                flush=True,
            )

    finished_at = datetime.now(timezone.utc).isoformat()
    elapsed_total = time.perf_counter() - t_start

    new_aggregate = aggregate(new_records)

    out_payload = dict(payload)
    out_payload["records"] = new_records
    out_payload["aggregate"] = new_aggregate

    # Preserve the original meta but add a re-judge sub-block so a
    # downstream consumer can tell when re-judge ran and which model.
    meta = dict(payload.get("meta") or {})
    meta["re_judge"] = {
        "model": model,
        "timeout": timeout,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round(elapsed_total, 2),
        "n_records": len(new_records),
        "llm_judge_calls": judge.llm_judge_calls,
        "llm_judge_failures": judge.llm_judge_failures,
        "input_path": str(input_path),
        "limit": limit,
    }
    out_payload["meta"] = meta

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=Path, required=True, help="Existing result JSON.")
    parser.add_argument("--output", type=Path, required=True, help="Path to write augmented JSON.")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-6", help="Judge model.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-call timeout seconds.")
    parser.add_argument("--limit", type=int, default=None, help="Only re-judge first N records (smoke).")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print a progress line every N records (0 = silent).",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"Input not found: {args.input}")

    payload = re_judge(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        timeout=args.timeout,
        limit=args.limit,
        progress_every=args.progress_every,
    )

    agg = payload["aggregate"]["overall"]
    rj = payload["meta"].get("re_judge", {})
    failed_pct = agg.get("llm_judge_failed_pct", 0.0)
    print(
        f"Wrote {args.output} — n={agg['n']} "
        f"f1={agg.get('f1', 0):.3f} "
        f"llm_judge_correct={agg.get('llm_judge_correct_pct', 0):.3f} "
        f"partial={agg.get('llm_judge_partial_pct', 0):.3f} "
        f"wrong={agg.get('llm_judge_wrong_pct', 0):.3f} "
        f"failed={failed_pct:.3f} "
        f"| calls={rj.get('llm_judge_calls', 0)} fails={rj.get('llm_judge_failures', 0)} "
        f"elapsed={rj.get('elapsed_seconds', 0)}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

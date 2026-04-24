"""Run a single benchmark version against the LoCoMo dataset.

Usage:
    python -m benchmarks.harness.runner \
        --config benchmarks/configs/v0_baseline.yaml \
        --dataset benchmarks/datasets/locomo \
        --output benchmarks/results/v0_<timestamp>.json \
        --limit 10

Output JSON shape::

    {
      "meta": {
        "config_name": "v0_baseline",
        "dataset_path": "...",
        "started_at": "...",
        "finished_at": "...",
        "n_samples": 10,
        "n_questions": 175
      },
      "records": [
        {
          "sample_id": "conv-1",
          "question": "...",
          "expected_answer": "...",
          "agent_answer": "...",
          "category": "temporal",
          "elapsed_ms": 42,
          "tokens": {"prompt": 0, "completion": 0},  # filled in when v1 wired
          "scores": {"f1": ..., "bleu1": ..., "rougeL": ..., "llm_judge": null},
          "retrieved_count": 5
        }
      ],
      "aggregate": {...}
    }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running via ``python -m benchmarks.harness.runner`` from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.harness.adapter import LoCoMoAdapter, LoCoMoSample, load_samples
from benchmarks.harness.judge import Judge, aggregate


def _load_config(path: Path) -> Dict[str, Any]:
    """Load a YAML config without requiring pyyaml.

    We keep the configs minimal (flat key: value) and use a stdlib-only
    micro-parser so the harness has no extra install step. If a future
    config needs nested structures, upgrade to pyyaml and pin in
    requirements-dev.txt.
    """
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(raw) or {}
    except Exception:
        pass

    # Minimal fallback parser: ``key: value`` and ``key:`` + nested ``  k: v``.
    result: Dict[str, Any] = {}
    stack: List[tuple] = [(0, result)]
    for line_no, raw_line in enumerate(raw.splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Pop stack back to the right level.
        while stack and stack[-1][0] > indent:
            stack.pop()
        parent = stack[-1][1]

        if value == "":
            new_dict: Dict[str, Any] = {}
            parent[key] = new_dict
            stack.append((indent + 2, new_dict))
        else:
            parent[key] = _coerce(value)
    return result


def _coerce(raw: str) -> Any:
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if raw.lower() in {"null", "none", "~"}:
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw.strip('"').strip("'")


def _find_dataset_file(dataset_path: Path) -> Path:
    """Locate the LoCoMo JSON inside *dataset_path*.

    Accepts either the directory (in which case we pick the first *.json)
    or a direct path to a JSON file.
    """
    if dataset_path.is_file():
        return dataset_path
    candidates = sorted(dataset_path.glob("*.json"))
    if not candidates:
        raise SystemExit(
            f"No JSON found in {dataset_path}. Run "
            f"`python benchmarks/datasets/download_locomo.py` first."
        )
    return candidates[0]


def run(
    config: Dict[str, Any],
    dataset_path: Path,
    output_path: Path,
    limit: Optional[int] = None,
    config_name: str = "unknown",
    qa_limit: Optional[int] = None,
) -> Dict[str, Any]:
    dataset_file = _find_dataset_file(dataset_path)
    samples = load_samples(dataset_file)
    if limit is not None:
        samples = samples[:limit]

    memory_cfg = config.get("memory", {}) or {}
    top_k = int(memory_cfg.get("top_k", 5))
    collection = str(memory_cfg.get("collection", "conversations"))

    adapter = LoCoMoAdapter(top_k=top_k, collection=collection)
    judge = Judge()  # LLM judge stays disabled until wired up.

    records: List[Dict[str, Any]] = []
    cli_errors: List[Dict[str, Any]] = []
    rerank_notes_all: List[Dict[str, Any]] = []
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        for sample in samples:
            session_id = adapter.prepare_memory(sample)
            qa_iter = sample.qa if qa_limit is None else sample.qa[:qa_limit]
            for qa in qa_iter:
                t0 = time.perf_counter()
                result = adapter.query(session_id, qa.question, config=config)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)

                scores = judge.score(
                    question=qa.question,
                    expected=qa.answer,
                    actual=result["answer"],
                    category=qa.category,
                )
                records.append(
                    {
                        "sample_id": sample.sample_id,
                        "question": qa.question,
                        "expected_answer": qa.answer,
                        "agent_answer": result["answer"],
                        "category": qa.category,
                        "elapsed_ms": elapsed_ms,
                        # Token counts are unavailable when answers come
                        # from `claude -p` subprocess (no stats on stdout);
                        # fill with -1 so downstream consumers can detect
                        # "not measured" vs "zero".
                        "tokens": {"prompt": -1, "completion": -1},
                        "scores": scores,
                        "retrieved_count": result["n_retrieved"],
                        "cli_error": result.get("cli_error"),
                    }
                )
                if result.get("cli_error"):
                    cli_errors.append(
                        {
                            "sample_id": sample.sample_id,
                            "question": qa.question,
                            "error": result["cli_error"],
                        }
                    )
                if result.get("rerank_notes"):
                    rerank_notes_all.append(
                        {
                            "sample_id": sample.sample_id,
                            "question": qa.question,
                            "notes": result["rerank_notes"],
                        }
                    )
            adapter.cleanup(session_id)
    finally:
        adapter.cleanup_all()

    finished_at = datetime.now(timezone.utc).isoformat()
    elapsed_list = [r["elapsed_ms"] for r in records if r.get("elapsed_ms") is not None]
    elapsed_stats: Dict[str, Any] = {}
    if elapsed_list:
        s = sorted(elapsed_list)
        n = len(s)
        mean = sum(s) / n
        p95 = s[min(n - 1, int(0.95 * n))]
        elapsed_stats = {
            "n": n,
            "mean_ms": round(mean, 2),
            "p50_ms": s[n // 2],
            "p95_ms": p95,
            "max_ms": s[-1],
        }

    payload = {
        "meta": {
            "config_name": config_name,
            "dataset_path": str(dataset_file),
            "started_at": started_at,
            "finished_at": finished_at,
            "n_samples": len(samples),
            "n_questions": len(records),
            "limit": limit,
            "elapsed_stats": elapsed_stats,
            "cli_calls": adapter.cli_calls,
            "cli_failures": adapter.cli_failures,
            "cli_errors": cli_errors,
            "rerank_notes": rerank_notes_all,
        },
        "config": config,
        "records": records,
        "aggregate": aggregate(records),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _default_output(config_name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return _REPO_ROOT / "benchmarks" / "results" / f"{config_name}_{ts}.json"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a YAML config (e.g. benchmarks/configs/v0_baseline.yaml).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=_REPO_ROOT / "benchmarks" / "datasets" / "locomo",
        help="Dataset directory or direct JSON path (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: benchmarks/results/<config>_<ts>.json).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N samples (useful for smoke tests).",
    )
    parser.add_argument(
        "--qa-limit",
        type=int,
        default=None,
        help="Only run the first N QA items per sample (useful for smoke tests where a sample has 100+ questions).",
    )
    args = parser.parse_args(argv)

    config_path: Path = args.config
    if not config_path.exists():
        parser.error(f"Config not found: {config_path}")
    config = _load_config(config_path)
    config_name = config.get("name") or config_path.stem

    output_path = args.output or _default_output(config_name)

    payload = run(
        config=config,
        dataset_path=args.dataset,
        output_path=output_path,
        limit=args.limit,
        config_name=config_name,
        qa_limit=args.qa_limit,
    )

    agg = payload["aggregate"]["overall"]
    meta = payload["meta"]
    el = meta.get("elapsed_stats") or {}
    print(
        f"Wrote {output_path} — n={agg['n']} "
        f"f1={agg['f1']:.3f} bleu1={agg['bleu1']:.3f} rougeL={agg['rougeL']:.3f} "
        f"| mean={el.get('mean_ms', 0)}ms p95={el.get('p95_ms', 0)}ms "
        f"| cli {meta.get('cli_calls', 0)} calls, {meta.get('cli_failures', 0)} failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

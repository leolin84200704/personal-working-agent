# LoCoMo Benchmark Harness

Skeleton harness for running the [LoCoMo](https://github.com/snap-research/locomo)
long-conversation-memory benchmark against lis-code-agent's memory system.

Goal: compare **v0 (pre-Hermes baseline)** vs **v1 (post-Hermes)** on the
same set of long multi-session dialogues, producing a diffable JSON per
run and a markdown summary.

## Layout

```
benchmarks/
├── README.md                 # this file
├── datasets/
│   ├── download_locomo.py    # fetches locomo10.json from upstream
│   └── locomo/               # downloaded JSON lives here (gitignored)
├── harness/
│   ├── adapter.py            # LoCoMo -> per-sample isolated memory store
│   ├── runner.py             # runs one config, writes results JSON
│   ├── judge.py              # F1 / BLEU-1 / ROUGE-L + LLM judge stub
│   └── compare.py            # diff two result JSONs into markdown
├── results/                  # output JSONs land here
└── configs/
    ├── v0_baseline.yaml      # current lis-code-agent settings
    └── v1_hermes.yaml        # placeholder (TODO)
```

## Quick start

```bash
# 1. Fetch the data (~1-3 MB, excluded from git)
python benchmarks/datasets/download_locomo.py

# 2. Smoke test the CLI
python -m benchmarks.harness.runner --help

# 3. Run v0 on 2 samples (fast)
python -m benchmarks.harness.runner \
    --config benchmarks/configs/v0_baseline.yaml \
    --dataset benchmarks/datasets/locomo \
    --output benchmarks/results/v0_smoke.json \
    --limit 2

# 4. (later) run v1 and diff
python -m benchmarks.harness.compare \
    benchmarks/results/v0_smoke.json \
    benchmarks/results/v1_smoke.json \
    --output benchmarks/results/diff.md
```

## Adding a new version (e.g. v1)

1. Land the new code path under `src/memory/`.
2. Copy `configs/v0_baseline.yaml` to a new file, e.g. `v1_hermes.yaml`,
   and adjust the keys that differ (`top_k`, `rerank`, `llm_judge_*`, etc.).
3. If the new pipeline needs a different adapter hook (e.g. the agent
   loop instead of raw vector store), extend `harness/adapter.py`:
   dispatch based on `config.get("adapter", "vector_store")`.
4. Run the harness with the new config, then `compare.py` the outputs.

## v0 vs v1 — what actually changes

| Axis | v0 baseline | v1 Hermes (planned) |
|---|---|---|
| Retrieval | top-k nearest neighbours in ChromaDB | scored + re-ranked via consolidator |
| Ingest | one doc per dialogue turn | dreaming pipeline consolidates sessions |
| Answering | concat top-k turns as "answer" | real agent loop + LLM |
| Judge | F1 / BLEU-1 / ROUGE-L only | + LLM-as-judge |
| Token accounting | zeros (no LLM call) | real prompt + completion counts |

v0 is deliberately a lower bound: no agent, no LLM, no scoring. Its job is
to anchor the chart so v1 lift is unambiguous.

## Known limitations

- **LoCoMo is a dialogue benchmark; lis-code-agent is ticket-based.**
  The adapter papers over this by treating each LoCoMo turn like a
  conversation fragment stored in the `conversations` Chroma collection.
  We do **not** route anything through STM files or the auto-dream
  pipeline, because those are keyed on `ticket_id`.
- **No LLM at query time in v0.** The returned "answer" is literally the
  concatenated top-k retrieved turns. String-overlap metrics therefore
  reward retrieval that happens to contain the gold answer verbatim.
- **LLM-as-judge is a stub.** Interface is designed but the Anthropic
  call is not wired up; needs an API key and a model choice from Leo.
- **Namespace isolation via separate Chroma dirs.** `VectorStore`'s
  collection names are hard-coded attributes, so we create a fresh
  `VectorStore` rooted at `benchmarks/results/_chroma_sandbox/<session>/`
  per sample and drop it on cleanup. The real agent's `storage/chroma`
  is never touched.
- **Python 3.9-safe.** Uses `from __future__ import annotations` instead
  of PEP 604 unions, to match the project's `python3` (3.9.6).

## Dependencies

The harness itself is stdlib-only except for what `src/memory/` already
requires (`chromadb`, `sentence-transformers`). No new entries added to
`requirements.txt`. If LLM judging lands, add `anthropic` (already in
the project's `requirements.txt`).

## Not in git

Downloaded data files are excluded. See the top-level `.gitignore`:

```
benchmarks/datasets/locomo/*.json
benchmarks/results/_chroma_sandbox/
benchmarks/results/*.json
```

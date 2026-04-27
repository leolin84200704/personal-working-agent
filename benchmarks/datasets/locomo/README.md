# LoCoMo Dataset

LoCoMo (Long Conversation Memory) is a benchmark for evaluating long-term
memory in conversational agents.

## Source
- Paper: "Evaluating Very Long-Term Conversational Memory of LLM Agents" (SNAP Research, 2024)
- GitHub: https://github.com/snap-research/locomo
- License: See upstream repo. Redistributable for research use; check the
  upstream LICENSE before redistributing derivatives.

## Download
```bash
python benchmarks/datasets/download_locomo.py
```

This writes `locomo10.json` (the primary 10-sample benchmark file used in
the paper) into this directory. The JSON is excluded from git by
`.gitignore` to keep the repo lean.

## Data format (expected; verify after download)
Each sample is roughly shaped like:

```json
{
  "sample_id": "conv-1",
  "conversation": {
    "session_1": [
      {"speaker": "A", "dia_id": "D1:1", "text": "...", "img_url": null},
      {"speaker": "B", "dia_id": "D1:2", "text": "..."}
    ],
    "session_1_date_time": "2023-05-01T10:00:00",
    "session_2": [...],
    "session_2_date_time": "2023-05-08T09:00:00"
  },
  "qa": [
    {"question": "...", "answer": "...", "category": 1, "evidence": ["D1:3"]}
  ]
}
```

`category` (per upstream):
- 1: Single-hop
- 2: Multi-hop
- 3: Temporal
- 4: Open-domain / commonsense
- 5: Adversarial (no answer in the conversation)

The actual schema may vary; `download_locomo.py` prints a shallow sanity
summary (top-level keys, number of samples, sha256 prefix) so you can
confirm what you actually got before wiring the adapter.

## Size
`locomo10.json` is roughly 1-3 MB. It has 10 long multi-session dialogues,
each with ~300 turns split across ~35 sessions, and ~200 QA pairs total.

## Not in git
The JSON files are listed in the repo `.gitignore`
(`benchmarks/datasets/locomo/*.json`). Only this README and `.gitkeep`
are tracked.

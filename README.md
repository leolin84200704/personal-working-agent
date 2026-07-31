# LIS Code Agent

AI agent for Leo's LIS (Laboratory Information System) work: Jira ticket processing, EMR integrations, and code changes across the LIS repos — with a file-based, self-consolidating memory system.

**How it actually runs (v3): Claude Code + markdown.** There is no long-running service. You open Claude Code in this repo; `CLAUDE.md` defines the role and the 9-step work loop, `RETRIEVAL.md` defines how memory is read/written, and a nightly `claude -p` job consolidates memory. Everything under `src/` is the retired v2 Python service — see [Legacy](#legacy-v2-python-service) below.

## Usage

```bash
cd vibrant-america-working-agent
claude
# then: 「處理 VP-xxxxx」 / 「VP-xxxxx 現在到哪了」 / 「掃一下我的 open tickets」
```

The work loop (analyze → debate → confirm → execute → review → retrospective → journal) and all behavior rules live in `CLAUDE.md`. Retrieval discipline — which memory layer answers which question, and when Jira/GitHub must be checked as ground truth — lives in `RETRIEVAL.md`.

## Memory architecture

| Layer | Path | Role | Written by |
|---|---|---|---|
| L2 indexes | `*/_index.md` | Scored routing tables | Dream pipeline |
| L3a episodic | `journal/` | Session reasoning traces (explored / ruled out / decided / why) | Agent, end of session |
| L3b task | `storage/short_term_memory/{ticket}.md` | Per-ticket work record | Agent during work |
| L3b rules | `long-term-memory/` | Distilled knowledge | **Dream only** (agent never writes LTM directly) |
| Archive | `archive/` | Completed, low-score memories | Dream |
| L4 | Jira / GitHub / repos / prod | Ground truth | External |

Scoring formula and thresholds: see `scripts/memory_scoring.py` docstring.

## Dream pipeline (nightly consolidation)

Runs `claude -p "$(cat scripts/dream.md)"` daily at 18:30 via launchd:

- **Phase 0** — reconcile STM status against live Jira (`scripts/reconcile-jira.py`, needs `.env` with `JIRA_SERVER` / `JIRA_EMAIL` / `JIRA_API_TOKEN`)
- **Phase 1-3** — incremental consolidation: distill journals → LTM, extract lessons, merge, archive, forget
- **Phase 4** — `scripts/memory_scoring.py`: auto-link, rescore, rebuild indexes (standalone, no `src/` dependency)
- **Phase 5** — dream log to `logs/dream-YYYY-MM-DD.md`

```bash
bash scripts/install-launchd.sh      # install/refresh launchd jobs FOR THIS MACHINE's path
bash scripts/install-launchd.sh --status
./scripts/run-dream.sh               # manual trigger
./scripts/run-dream.sh --dry
```

**Liveness**: the pipeline died silently for 3 weeks in June 2026 (plist hardcoded another machine's path; failures were misread as success). Guards now in place: `install-launchd.sh` generates the plist from the current checkout path; `run-dream.sh` checks the `claude` binary and exit codes and raises a macOS notification on failure; every Claude Code session checks the STM index `Last updated:` date at session start and flags staleness > 3 days (see `RETRIEVAL.md` § Staleness check).

A weekly self-improvement routine (`scripts/weekly-routine.sh`, Sunday 11:00) refreshes derived LTM files and captures eval snapshots.

## Repo layout

```
CLAUDE.md                    # role + work loop (auto-loaded by Claude Code)
RETRIEVAL.md                 # memory retrieval protocol (read this first)
AGENTS.md                    # subagent patterns used by the work loop
storage/short_term_memory/   # per-ticket records + _index.md
long-term-memory/            # distilled knowledge (knowledge/ is a symlink here)
journal/                     # episodic session traces
archive/                     # aged-out memories
skills/                      # skill definitions (work-loop, emr-integration, git, ...)
scripts/                     # dream.md, run-dream.sh, memory_scoring.py,
                             # reconcile-jira.py, install-launchd.sh, weekly-routine.sh
docs/                        # architecture notes, ticket reports, vendor PDFs
DailyJob/                    # HL7 triage runners
logs/                        # dream + launchd logs
legacy/                      # one-off scripts from the v2 era
src/, tests/, start_agent.py # v2 Python service (retired, see below)
```

## Git safety

Enforced by PreToolUse hooks in `.claude/settings.json` (`.claude/hooks/validate-git-*.sh`):

- Allowed: `feature/leo/*`, `bugfix/leo/*` branches; push only to own branches
- Blocked: force push, `reset --hard`, `clean -f`, direct push to main/master/staging
- The agent never merges — Leo decides

## Legacy (v2 Python service)

`src/` contains the retired FastAPI/WebSocket agent (agent loop, session index, thread-safe git operator). It is **not maintained and not part of the running system**. It stays in the tree because `scripts/eval.py` and `scripts/test-retrieval.py` still import parts of it (memory manager/scorer) for benchmark snapshots. Do not add new dependencies on `src/` — the dream pipeline was deliberately decoupled from it (`scripts/memory_scoring.py`). The ChromaDB/`all-MiniLM-L6-v2` vector store was DELETED on 2026-07-30 (never invoked by the running system; English-only model on a mixed 繁中/English corpus); some retired modules still carry dead imports of it and will not start — they are not meant to.

The RAG/embedding chain (SentenceTransformer → ChromaDB semantic search) was replaced by Grep + scored `_index.md` routing, which is transparent, diffable, and has no model/index to drift. If semantic search is ever needed again, build it as a standalone script with a **multilingual** embedding model — the memory corpus is mixed 繁中/English and `all-MiniLM-L6-v2` is English-only, so its recall on Chinese memory text was always weak.

Internal use only.

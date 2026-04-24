# Auto Dream Architecture — Technical Design Document

> A comprehensive reference for the personal-agent's memory consolidation system,
> covering architecture, framework choices, implementation, and academic foundations.

**Version:** 1.0
**Date:** 2026-04-22
**Author:** Leo (Hung-Fan Lin)

---

## Table of Contents

1. [Motivation & Problem Statement](#1-motivation--problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Memory Tier Design](#3-memory-tier-design)
4. [Dreaming Pipeline](#4-dreaming-pipeline)
5. [Scoring & Retrieval Model](#5-scoring--retrieval-model)
6. [Forgetting Curve & Lifecycle](#6-forgetting-curve--lifecycle)
7. [Cross-Linking (Zettelkasten Graph)](#7-cross-linking-zettelkasten-graph)
8. [Framework & Technology Stack](#8-framework--technology-stack)
9. [Execution Infrastructure](#9-execution-infrastructure)
10. [Token Efficiency Strategies](#10-token-efficiency-strategies)
11. [Academic References](#11-academic-references)
12. [Future Directions](#12-future-directions)

---

## 1. Motivation & Problem Statement

LLM-based personal agents face a fundamental tension: **context windows are finite, but life is not.**

Without active memory management, agent memory systems suffer from:

| Problem | Symptom |
|---------|---------|
| **Accumulation bloat** | Files pile up; every session loads stale context |
| **Flat retrieval** | No prioritization — immigration deadlines treated same as old reminders |
| **No consolidation** | Repeated patterns stay as N separate files instead of one insight |
| **No forgetting** | Token budget wasted on irrelevant, outdated information |
| **Isolated memories** | Related files have no linkage; context is fragmented |

**Auto Dreaming** solves this by borrowing from neuroscience: during "sleep" (idle time between sessions), the agent consolidates episodic memories into semantic knowledge, prunes irrelevant details, and reorganizes connections — just like the human brain does during REM sleep.

---

## 2. Architecture Overview

```
                          ┌─────────────────────────┐
                          │     INPUT CHANNELS       │
                          │  CLI · Telegram · Cron   │
                          └───────────┬─────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │          WORKING MEMORY              │
                    │  (in-session context window)         │
                    │  • Current conversation              │
                    │  • Active tool results               │
                    │  • Loaded memory (scored, top-K)     │
                    └───────────────┬─────────────────────┘
                                    │ session ends
                                    ▼
          ┌──────────────────────────────────────────────────┐
          │              SHORT-TERM MEMORY                    │
          │  short-term-memory/*.md                           │
          │  • Active tasks, deadlines, raw observations      │
          │  • Lifespan: < 3 months                           │
          │  • Granular, action-oriented                      │
          └───────────────┬──────────────────────────────────┘
                          │
                    ┌─────┴──────┐
                    │  DREAMING  │  ◀── daily 8 PM (launchd)
                    │  PIPELINE  │      or manual trigger
                    └─────┬──────┘
                          │
          ┌───────────────┼───────────────────┐
          ▼               ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  LONG-TERM   │  │   ARCHIVE    │  │   FORGET     │
│   MEMORY     │  │  archive/    │  │  (deleted)   │
│              │  │              │  │              │
│ Consolidated │  │ Completed/   │  │ Irrelevant   │
│ patterns &   │  │ stale items  │  │ superseded   │
│ preferences  │  │ score < 0.1  │  │ score < 0.05 │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## 3. Memory Tier Design

Inspired by **MemoryOS** (EMNLP 2025) — a 3-tier hierarchical memory management system modeled after operating system memory management.

### Tier 1: Working Memory (Ephemeral)
- **Scope:** current conversation context window
- **Content:** loaded memory snippets, tool results, conversation history
- **Lifespan:** single session
- **Budget:** ~2000 tokens allocated to pre-loaded memory

### Tier 2: Short-Term Memory (Active)
- **Location:** `short-term-memory/*.md`
- **Content:** active tasks, upcoming events, raw observations from integrations
- **Lifespan:** < 3 months (governed by forgetting curve)
- **Character:** granular, specific, action-oriented
- **Scoring half-life:** 30 days

### Tier 3: Long-Term Memory (Persistent)
- **Location:** `long-term-memory/*.md`
- **Content:** consolidated patterns, verified preferences, life context, identity info
- **Lifespan:** persistent with decay scoring (immigration/legal items never decay)
- **Character:** abstract, semantic, context-providing
- **Scoring half-life:** 180 days

### Tier 4: Archive & Forget
- **Archive** (`archive/`): completed/stale items below active threshold, still retrievable on demand
- **Forget** (deleted): truly irrelevant or fully superseded memories, removed permanently

---

## 4. Dreaming Pipeline

The dreaming process is a 5-phase consolidation cycle inspired by **Mem0**'s production consolidation pipeline and **Active Dreaming Memory** research on counterfactual verification.

### Phase 1: Orient
```
Read short-term-memory/_index.md
Read long-term-memory/_index.md
Read all individual *.md files in both directories
Read FEEDBACK.md for behavioral constraints
Note current date for all time-based calculations
```

### Phase 2: Gather Signal
For each short-term file, classify:

| Signal Type | Criteria | Example |
|-------------|----------|---------|
| `completed` | status=done | Finished task with no ongoing relevance |
| `approaching` | deadline < 2 weeks | SEVIS transfer deadline nearing |
| `lasting_insight` | Contains reusable pattern/preference | User consistently prefers X |
| `overlap` | Duplicates info in another file | Two notes about same trip |
| `stale` | Not updated in > 60 days, not blocking | Old one-time reminder |

### Phase 3: Consolidate
Seven atomic operations:

| # | Operation | Trigger | Action |
|---|-----------|---------|--------|
| 1 | **Extract** | Completed task contains lasting insight | Pull knowledge → long-term memory |
| 2 | **Merge** | Two+ files cover same topic | Combine into one, delete redundant |
| 3 | **Update** | File has relative dates or stale info | Fix dates, update facts |
| 4 | **Resolve** | New info contradicts old | Trust newer verified source |
| 5 | **Promote** | Pattern appears 3+ times in short-term | Create long-term pattern note |
| 6 | **Archive** | status=done AND updated > 30 days ago | Move to `archive/` |
| 7 | **Forget** | Score < 0.05 for > 180 days (non-immigration) | Delete permanently |

### Phase 4: Score & Reindex
- Recalculate importance scores for all active files (see Section 5)
- Rebuild `_index.md` as scored routing tables, sorted descending
- Add/update cross-links between related files (see Section 7)

### Phase 5: Log
Generate `logs/dream-YYYY-MM-DD.md` with:
- Files scanned, archived, promoted, merged, updated
- Score statistics (highest, lowest, median)
- Memory stats (file counts per tier)

### Idempotency Guarantee
Running the dream pipeline twice on the same day produces the same result. All operations are idempotent by design — scoring is deterministic, archival checks are absolute-date-based, and index rebuilds are full replacements.

---

## 5. Scoring & Retrieval Model

Inspired by **Generative Agents** (Stanford, UIST 2023) — retrieval scoring based on recency, importance, and relevance — combined with **Sleep-time Compute** (UC Berkeley, 2025) for pre-processing during idle time.

### Importance Score Formula

```
score = (base_weight × recency_factor × reference_boost) / normalization

Where:
  base_weight     ∈ {immigration: 1.0, work: 0.9, finance: 0.8,
                     health: 0.7, education: 0.7, personal: 0.6}

  recency_factor  = e^(-days_since_update / half_life)
                    half_life = 30 (short-term) | 180 (long-term)

  reference_boost = 1.0 + (0.1 × incoming_link_count)

  normalization   = 8.0
```

### Score Range Examples

| Scenario | base | recency | boost | score |
|----------|------|---------|-------|-------|
| Immigration task, updated today, 2 links | 1.0 | 1.0 | 1.2 | 0.15 |
| Personal task, 30 days old, 0 links | 0.6 | 0.37 | 1.0 | 0.03 |
| Work task, 7 days old, 1 link | 0.9 | 0.79 | 1.1 | 0.10 |

### Retrieval Strategy (Session Start)

```
1. ALWAYS load: _index.md files (lightweight routing tables)
2. ALWAYS load: AGENT.md, FEEDBACK.md (behavioral rules)
3. SCORE all memories against current query/context
4. LOAD top-K files where score > threshold
5. ENFORCE token budget: max ~2000 tokens
6. ON-DEMAND: retrieve additional files if conversation requires
```

This is analogous to **Sleep-time Compute**: the dreaming process pre-digests context so that session-start retrieval is fast and token-efficient, rather than loading raw data and processing in real-time.

---

## 6. Forgetting Curve & Lifecycle

Modeled after Ebbinghaus forgetting curve, with configurable thresholds:

```
Score
1.0  ┤ ████
     │  ████
0.5  ┤    ████
     │      ████
0.1  ┤        ████████████
     │                    ████──── archive threshold (score < 0.1, age > 90d)
0.05 ┤
     │                         ███──── forget threshold (score < 0.05, age > 180d)
0.0  ┤
     └──┬──┬──┬──┬──┬──┬──┬──→ Days
        7  14 30 60 90 120 180
```

### Lifecycle State Machine

```
              create
                │
                ▼
┌──────────┐  update  ┌──────────┐
│  ACTIVE  │ ───────▶ │  ACTIVE  │ (score refreshed)
│ (short)  │          │ (short)  │
└────┬─────┘          └────┬─────┘
     │ done + 30d          │ insight detected
     ▼                     ▼
┌──────────┐         ┌──────────┐
│ ARCHIVED │         │ PROMOTED │ → long-term-memory/
│ archive/ │         │ (long)   │
└────┬─────┘         └──────────┘
     │ score < 0.05 + 180d
     ▼
┌──────────┐
│ FORGOTTEN│ (deleted)
│          │
└──────────┘

Exception: immigration/legal items → NEVER auto-forget
```

---

## 7. Cross-Linking (Zettelkasten Graph)

Inspired by **A-MEM** (NeurIPS 2025) — Agentic Memory with Zettelkasten-style self-organizing cross-links.

### Mechanism
- Each memory file has a `links:` field in YAML frontmatter
- Links are bidirectional references to related memory file IDs
- During dreaming, the agent scans for thematic connections and updates links
- Linked memories receive a retrieval boost (`reference_boost` in scoring formula)

### Link Graph Example

```
  personal-info.md ◄────────► immigration-timeline.md
         │                          │
         │                     ┌────┴────┐
         │                     ▼         ▼
         │            sevis-transfer.md  vibrant-opt-form.md
         │                     │
         ▼                     ▼
  upcoming-visits.md    toyota-maintenance.md
```

### Benefits
- **Contextual retrieval**: query about SEVIS → automatically pulls immigration-timeline as context
- **Deduplication**: link to related file instead of copying content
- **Emergent structure**: the memory graph self-organizes over time through dreaming cycles

---

## 8. Framework & Technology Stack

### Core Runtime

| Component | Technology | Role |
|-----------|-----------|------|
| LLM Engine | Claude (Anthropic) via `claude` CLI | Dreaming agent execution, all reasoning |
| CLI Interface | Claude Code | Primary interactive interface |
| Mobile Interface | Telegram Bot (python-telegram-bot) | Mobile access to memory & tasks |
| API Integration | Claude API (Anthropic SDK) | Bot's LLM backend |
| Memory Store | Markdown files (YAML frontmatter) | Structured, version-controlled, human-readable |
| External Data | MCP Servers | Gmail, Calendar, Finance (planned) |
| Scheduling | macOS launchd | Daily dream trigger at 8 PM PT |
| Version Control | Git | Memory history, diff tracking |

### Why Markdown + YAML Frontmatter?

Chosen over databases or vector stores for this use case because:

1. **Human-readable & editable** — user can manually inspect/edit any memory
2. **Git-friendly** — full history, diffs, rollback for every memory change
3. **LLM-native** — Claude can read/write Markdown natively without serialization
4. **Zero infrastructure** — no database server, no embedding model, no vector index
5. **Portable** — works across Claude Code CLI, Telegram bot, and scheduled scripts
6. **Structured enough** — YAML frontmatter provides typed metadata for scoring/filtering

### Why Not Vector Databases?

| Factor | Vector DB (e.g., Chroma, Pinecone) | Markdown Files |
|--------|-------------------------------------|----------------|
| Semantic search | Native | Manual (via LLM scoring) |
| Human readability | Poor | Excellent |
| Git integration | Not practical | Native |
| Infrastructure | Requires server/embedding model | None |
| Multi-channel access | Needs API wrapper | Direct file read |
| Scale needed | Designed for millions of records | ~50-200 files max |

For a personal agent with < 200 memory files, the overhead of a vector DB is unjustified. The scoring formula + LLM-based relevance judgment provides sufficient retrieval quality.

### MCP (Model Context Protocol) Integration

```
┌─────────────┐     MCP      ┌──────────────────┐
│ Claude Code  │ ──────────▶ │ Gmail MCP Server  │
│ / Telegram   │             │ (autoauth)        │
│   Bot        │             └──────────────────┘
│              │     MCP      ┌──────────────────┐
│              │ ──────────▶ │ GCal MCP Server   │ (planned)
│              │             └──────────────────┘
│              │     MCP      ┌──────────────────┐
│              │ ──────────▶ │ Finance MCP       │ (planned)
└─────────────┘             └──────────────────┘
```

MCP servers provide standardized tool interfaces for external data. The dreaming process can also scan integration data for memory-worthy signals (e.g., recurring calendar events → promote to long-term patterns).

---

## 9. Execution Infrastructure

### launchd Configuration

The dream process runs as a macOS Launch Agent:

- **Plist:** `~/Library/LaunchAgents/com.personal-agent.dream.plist`
- **Schedule:** daily at 8:00 PM (America/Los_Angeles)
- **Mechanism:** launchd → `scripts/run-dream.sh` → `claude -p` with `scripts/dream.md`
- **Logs:** `logs/launchd-stdout.log`, `logs/dream-YYYY-MM-DD.md`

### Execution Flow

```
launchd (8 PM daily)
    │
    ▼
run-dream.sh
    │
    ├── Check: claude CLI in PATH?
    ├── Check: dream.md exists?
    │
    ▼
claude -p "$(cat scripts/dream.md)" --allowedTools "Read,Write,Edit,Glob,Grep,Bash"
    │
    ├── Phase 1: Orient (read all memory files)
    ├── Phase 2: Gather Signal (classify each file)
    ├── Phase 3: Consolidate (archive/merge/promote/update)
    ├── Phase 4: Score & Reindex (recalculate, rebuild _index.md)
    └── Phase 5: Log (write dream-YYYY-MM-DD.md)
```

### Manual Trigger

```bash
cd /Users/linhungfan/personal_project/personal-agent
./scripts/run-dream.sh          # full run
./scripts/run-dream.sh --dry    # preview command only
```

### Management Commands

```bash
# Check if dream agent is scheduled
launchctl list | grep personal-agent

# Temporarily disable
launchctl unload ~/Library/LaunchAgents/com.personal-agent.dream.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.personal-agent.dream.plist
```

---

## 10. Token Efficiency Strategies

A key design goal: minimize tokens loaded per session while maximizing relevance.

| Strategy | Estimated Savings | Mechanism |
|----------|-------------------|-----------|
| **Scored retrieval** | ~70% | Only load top-K relevant memories, not all files |
| **Summary-first loading** | ~50% | Read YAML frontmatter + Summary first; load Details on demand |
| **Structured frontmatter** | ~30% | Machine-parseable metadata vs. prose descriptions |
| **Cross-linking** | ~40% | Reference by ID instead of duplicating content across files |
| **Dreaming compression** | ~60% | Periodic merge of overlapping files, removal of redundancy |
| **Token budget cap** | Hard limit | Max ~2000 tokens of pre-loaded memory per session |

### Comparison with Related Systems

| System | Token Strategy | Our Approach |
|--------|---------------|--------------|
| **Mem0** (2025) | Embedding + consolidation → 90%+ reduction | Similar consolidation, but file-based instead of embedding |
| **E-mem** (2026) | Hierarchical architecture → >70% reduction | Same tier concept, simpler implementation |
| **Sleep-time Compute** (2025) | Pre-process during idle → 5x compute reduction | Dream cycle pre-digests context, same principle |
| **MAGMA** (2026) | Multi-graph adaptive traversal | Cross-linking provides lightweight graph traversal |

---

## 11. Academic References

The auto dream architecture draws from multiple lines of research in LLM agent memory systems. Below is a categorized reference list.

### Memory Architecture & Tier Design

| Paper | Key Contribution | Venue | Year |
|-------|------------------|-------|------|
| **MemoryOS** — Kang et al. | 3-tier hierarchical memory modeled after OS memory management (short-term / mid-term / long-term with promotion/demotion policies) | EMNLP 2025 Oral | 2025 |
| **E-mem** | Hierarchical memory architecture achieving >70% token reduction through structured storage and selective retrieval | arXiv:2601.21714 | 2026 |
| **Memory Survey** | Comprehensive taxonomy of LLM agent memory: factual, experiential, and working memory with full lifecycle analysis | arXiv:2512.13564 | 2025 |

### Memory Consolidation & Dreaming

| Paper | Key Contribution | Venue | Year |
|-------|------------------|-------|------|
| **Sleep-time Compute** — Lin, Snell, Wang et al. | Pre-process context during idle periods (between queries); achieves equivalent of 5x inference compute at fraction of cost. Direct inspiration for "dreaming during idle time" concept | arXiv:2504.13171 | 2025 |
| **Active Dreaming Memory** | Counterfactual verification before promoting memories to long-term storage — prevents hallucinated consolidation | engrXiv / ResearchGate (preprint) | 2025 |
| **Mem0** — Chhikara et al. | Production-ready memory consolidation pipeline with extract/merge/update/resolve operations; demonstrated 90%+ token savings in real deployments | arXiv:2504.19413 | 2025 |

### Memory Organization & Retrieval

| Paper | Key Contribution | Venue | Year |
|-------|------------------|-------|------|
| **Generative Agents** — Park, O'Brien, Cai et al. | Reflection-based memory consolidation with importance scoring. Introduced the recency × importance × relevance retrieval formula that our scoring model extends | UIST 2023 | 2023 |
| **A-MEM** — Xu, Liang et al. | Zettelkasten-inspired self-organizing memory with cross-linking. Memories form a connected graph; related memories boost each other's retrieval probability | NeurIPS 2025 | 2025 |
| **MAGMA** — Jiang et al. | Multi-graph memory with adaptive traversal policy — memories organized as four orthogonal graphs (semantic/temporal/causal/entity) with policy-guided retrieval | arXiv:2601.03236 | 2026 |

### Neuroscience Foundations

The "dreaming" metaphor is grounded in established neuroscience:

- **Memory consolidation during sleep** (Diekelmann & Born, 2010): sleep transforms labile episodic memories into stable semantic knowledge through hippocampal-neocortical dialogue
- **Synaptic homeostasis hypothesis** (Tononi & Cirelli, 2006): sleep prunes weak synaptic connections while preserving strong ones — analogous to our forgetting curve
- **REM sleep and creative connections** (Walker & Stickgold, 2010): REM sleep creates novel associations between distant memories — analogous to our cross-linking phase

---

## 12. Future Directions

### Near-term (In Progress)

- **Integration-aware dreaming:** After Gmail/Calendar/Finance integrations are live, the dream process will also scan integration data for memory-worthy signals
  - Recurring calendar events → promote to long-term patterns
  - Spending anomalies → create short-term alert tasks
  - Email patterns → detect relationship/context changes

### Medium-term (Planned)

- **Threshold-based triggers:** Auto-dream when short-term file count exceeds N (e.g., 15), in addition to scheduled runs
- **Semantic scoring enhancement:** Optionally use embedding similarity (local model) alongside the formula-based score for better retrieval
- **Dream quality metrics:** Track consolidation effectiveness over time (files merged, tokens saved, retrieval hit rate)

### Long-term (Research)

- **Multi-agent dreaming:** If multiple personal agents exist (e.g., work agent + life agent), cross-agent memory consolidation
- **Adaptive half-life:** Learn optimal forgetting rates per category from actual usage patterns
- **MAGMA-inspired graph traversal:** Replace simple link-boost with learned traversal policies for memory retrieval

---

*This document is maintained alongside the personal-agent codebase. For the operational memory architecture spec, see [`MEMORY-ARCHITECTURE.md`](../MEMORY-ARCHITECTURE.md). For the dream execution prompt, see [`scripts/dream.md`](../scripts/dream.md).*

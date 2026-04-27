# MEMORY — Knowledge Index

> Deprecated: 此檔案保留供向後相容。新的 scored index 在各 tier 的 `_index.md`。
> See CLAUDE.md for routing rules.

## Tier Index Locations

| Tier | Index | Content |
|------|-------|---------|
| STM | `storage/short_term_memory/_index.md` | Per-ticket work loop records |
| LTM | `long-term-memory/_index.md` | Consolidated knowledge (ex-knowledge/) |
| Archive | `archive/_index.md` | Completed, low-score memories |

## LTM Files (legacy routing table)

| File | When to Read |
|------|-------------|
| `long-term-memory/emr-integration.md` | EMR/integration/order/result/bundle tickets |
| `long-term-memory/repos.md` | Need to understand repo structure |
| `long-term-memory/ticket-routing.md` | Determine which repo a ticket maps to |
| `long-term-memory/patterns.md` | Common patterns, gotchas, env vars |

> Note: `knowledge/` is a symlink to `long-term-memory/`, old paths still work.

"""
Memory subsystem — 4-tier architecture: Working → STM → LTM → Archive.

Key modules:
  manager.py      - Path management, frontmatter I/O, tier listing
  scorer.py       - Importance scoring with recency decay and link boost
  consolidator.py - 7 consolidation operations for the dreaming pipeline
  linker.py       - Zettelkasten bidirectional cross-linking
  distiller.py    - LLM-based insight extraction (legacy, used by consolidator)
  short_term.py   - Per-ticket STM file management
"""

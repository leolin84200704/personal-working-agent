"""SQLite + FTS5 session index — Hermes-style lexical retrieval.

Stores conversation turns in a SQLite database with an FTS5 virtual table
for BM25-ranked full-text search. Designed to complement the chroma vector
store: vector search is great at fuzzy semantic matches; FTS5 is great at
keyword-exact and temporal vocabulary ("2 weeks ago", "7 May", names,
numbers) — exactly the categories where v0 vector retrieval scores worst.

The schema mirrors the spec in the v1-fts5 ticket:

    sessions(id, session_id, turn_index, speaker, text, turn_date,
             metadata_json, created_at)
    sessions_fts (FTS5 virtual table, content-linked to sessions)
    AFTER INSERT trigger keeps sessions_fts in sync.

Usage::

    idx = SessionIndex(Path("./storage/conversations/sessions.db"))
    idx.add("locomo-1", [
        {"text": "Hi", "speaker": "Alice", "date": "2023-05-07",
         "dia_id": "D2:1", "metadata": {"foo": "bar"}},
        ...
    ])
    hits = idx.search("hello", limit=10)

All writes funnel through ``security_scanner.scan()`` so prompt-injection /
credential / exfiltration payloads cannot land in the FTS index.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.memory.security_scanner import get_scanner

__all__ = ["SessionIndex", "escape_fts5_query"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    speaker TEXT,
    text TEXT NOT NULL,
    turn_date TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
    text,
    speaker,
    turn_date,
    content='sessions',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS sessions_ai AFTER INSERT ON sessions BEGIN
  INSERT INTO sessions_fts(rowid, text, speaker, turn_date)
  VALUES (new.id, new.text, new.speaker, new.turn_date);
END;

CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
"""


# ---------------------------------------------------------------------------
# FTS5 query escaping
# ---------------------------------------------------------------------------

# FTS5 query syntax is sensitive to a small set of special characters
# (double-quote, colon, parentheses, AND/OR/NOT/NEAR keywords, hyphens at
# token start, etc.). User-supplied questions like
# ``What's the date: 7 May?`` will explode if passed verbatim.
#
# Strategy: tokenise the query into "word-ish" tokens and either:
#   - quote each token as an FTS5 phrase (escaping internal `"` by doubling),
#     and OR them together; OR
#   - drop tokens that contain only special chars.
# This produces a permissive OR-of-phrases match that BM25 can rank.

# Strip everything that is not a letter/digit/whitespace/dash/underscore.
# ``unicode61`` tokenizer handles unicode letters, so we keep them all.
_TOKEN_PATTERN = re.compile(r"[^\w\s\-]+", flags=re.UNICODE)
# Tokens shorter than this are dropped (FTS5 won't index 1-char tokens
# meaningfully and they tend to add noise).
_MIN_TOKEN_LEN = 1


def escape_fts5_query(query: str) -> str:
    """Convert a raw user query into a safe FTS5 MATCH expression.

    - Strips FTS5-meta characters (`"`, `:`, `(`, `)`, `*`, etc.).
    - Splits on whitespace.
    - Wraps each surviving token in double quotes (FTS5 phrase syntax) and
      doubles any embedded `"` per FTS5 escape rules.
    - ORs the phrases together so any token can match (BM25 ranks).

    If the query has no usable tokens, returns an empty string so callers
    can short-circuit and skip the search.
    """
    if not query:
        return ""

    # Strip FTS5-meta punctuation. Keep word chars, whitespace, dash, underscore.
    cleaned = _TOKEN_PATTERN.sub(" ", query)
    tokens: List[str] = []
    for tok in cleaned.split():
        tok = tok.strip("-_")
        if len(tok) < _MIN_TOKEN_LEN:
            continue
        # FTS5 phrase escape: any `"` in the token must be doubled.
        # (After the meta-strip above this should never fire, but belt and braces.)
        tok = tok.replace('"', '""')
        tokens.append(f'"{tok}"')
    if not tokens:
        return ""
    return " OR ".join(tokens)


# ---------------------------------------------------------------------------
# SessionIndex
# ---------------------------------------------------------------------------


class SessionIndex:
    """SQLite + FTS5 backed session/turn store with BM25 search."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # ``check_same_thread=False`` matches chroma's behaviour and keeps
        # the harness flexible. The benchmark runner is single-threaded so
        # this is safe.
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, session_id: str, turns: Iterable[Dict[str, Any]]) -> int:
        """Add *turns* under *session_id*.

        Each turn dict may contain:
          - text (str, required, non-empty)
          - speaker (str, optional)
          - date / turn_date (str, optional ISO date)
          - dia_id (str, optional — copied into metadata)
          - metadata (dict, optional — JSON-encoded for storage)

        Every turn's text is run through ``security_scanner.scan()`` BEFORE
        it touches the DB. The scanner raises ``SecurityViolation`` on
        prompt-injection / credential-leak / exfiltration patterns, which
        propagates to the caller (fail-closed).

        Returns: number of rows inserted.
        """
        scanner = get_scanner()
        rows: List[tuple] = []

        for i, turn in enumerate(turns):
            text = str(turn.get("text", "")).strip()
            if not text:
                continue
            speaker = str(turn.get("speaker", "") or "")
            turn_date = str(turn.get("date", turn.get("turn_date", "")) or "")
            dia_id = str(turn.get("dia_id", "") or "")

            # Build metadata dict; preserve dia_id so callers can correlate
            # results back to the source turn.
            meta = dict(turn.get("metadata") or {})
            if dia_id and "dia_id" not in meta:
                meta["dia_id"] = dia_id
            metadata_json = json.dumps(meta, ensure_ascii=False) if meta else None

            # Security scan — fail-closed before the row is queued for INSERT.
            scanner.scan(
                text,
                context=f"session_index:add:{session_id}:{i}",
            )

            turn_index = int(turn.get("turn_index", i))
            rows.append(
                (session_id, turn_index, speaker, text, turn_date, metadata_json)
            )

        if not rows:
            return 0

        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO sessions
                    (session_id, turn_index, speaker, text, turn_date, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search over all sessions, BM25-ranked.

        Returns hits in the shape::

            {
              "text": str,
              "speaker": str,
              "turn_date": str,
              "metadata": dict,
              "rank": float,        # BM25 score (lower = better in FTS5)
              "session_id": str,
              "turn_index": int,
            }

        FTS5's bm25() returns NEGATIVE scores by default (more negative =
        more relevant); we expose the raw value as ``rank`` and sort
        ascending so callers get best-first ordering.

        Empty / unparseable queries return an empty list rather than
        raising, so the hybrid path can degrade gracefully.
        """
        match_expr = escape_fts5_query(query)
        if not match_expr:
            return []

        sql = """
            SELECT s.session_id, s.turn_index, s.speaker, s.text, s.turn_date,
                   s.metadata_json, bm25(sessions_fts) AS rank
            FROM sessions_fts
            JOIN sessions s ON s.id = sessions_fts.rowid
            WHERE sessions_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?
        """
        try:
            cur = self._conn.execute(sql, (match_expr, int(limit)))
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            # Last-line defence: even after escape_fts5_query, an exotic
            # query could still confuse the FTS5 parser. Treat as miss.
            return []

        out: List[Dict[str, Any]] = []
        for row in rows:
            metadata: Dict[str, Any] = {}
            if row["metadata_json"]:
                try:
                    metadata = json.loads(row["metadata_json"])
                except (ValueError, TypeError):
                    metadata = {}
            out.append(
                {
                    "text": row["text"],
                    "speaker": row["speaker"] or "",
                    "turn_date": row["turn_date"] or "",
                    "metadata": metadata,
                    "rank": float(row["rank"]),
                    "session_id": row["session_id"],
                    "turn_index": int(row["turn_index"]),
                }
            )
        return out

    def count(self) -> int:
        """Total number of indexed turns across all sessions."""
        cur = self._conn.execute("SELECT COUNT(*) FROM sessions")
        return int(cur.fetchone()[0])

    def clear(self) -> None:
        """Delete all rows. Mainly for tests and per-sample sandbox reset."""
        with self._conn:
            self._conn.execute("DELETE FROM sessions")
            # FTS5 contentless mirror: the AFTER INSERT trigger only handles
            # inserts, so we must wipe the FTS table explicitly. On a content
            # table FTS5 mirror this keeps rowids in sync with the deleted
            # sessions rows.
            self._conn.execute("DELETE FROM sessions_fts")

    def close(self) -> None:
        """Close the underlying SQLite connection. Safe to call repeatedly."""
        try:
            self._conn.close()
        except Exception:
            pass

    # Make the index work as a context manager for tests / scripts.
    def __enter__(self) -> "SessionIndex":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

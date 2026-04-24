"""LoCoMo -> lis-code-agent memory adapter.

Responsibilities
----------------
1. Load a LoCoMo sample (one long multi-session dialogue + QA pairs).
2. Inject that dialogue into an **isolated** lis-code-agent memory store so
   that different samples do not pollute each other.
3. Expose ``prepare_memory(sample) -> session_id`` and
   ``query(session_id, question, ...) -> answer`` so the runner is decoupled
   from memory internals.

Namespace isolation strategy
----------------------------
lis-code-agent's ``VectorStore`` exposes a fixed set of collections
(``conversations``, ``patterns``, ``gotchas``, ``code_snippets``) that are
bound to its Chroma persist directory. To keep benchmark runs from
polluting the real agent memory (and to keep samples independent), we
create a fresh ``VectorStore`` rooted at a per-sample temp directory:

    <persist_root>/<session_id>/chroma

where ``session_id`` is derived from ``sample_id``. ``cleanup(session_id)``
removes that directory. The singleton ``get_vector_store()`` is **not**
used here on purpose.

Retrieval modes (v0 upgrade)
----------------------------
- ``raw_vector`` (legacy): ``VectorStore.search(...)`` only — nearest
  neighbour over the conversations collection.
- ``retrieve_relevant_knowledge``: mirrors the agent's production
  retrieval path (distance + relevance_score fusion), run against the
  ``conversations`` collection that holds the LoCoMo turns. This reuses
  the exact formula from ``src/memory/indexer.py::retrieve_relevant_knowledge``,
  adapted to the collection the sandbox populates.

Re-ranking
----------
When enabled, the adapter runs ``MemoryScorer.score_file`` over each
retrieval hit. ``score_file`` is designed for YAML-frontmatter memory
files on disk, so the adapter writes each hit to a temp MD file with
synthetic frontmatter (id / updated / base_weight / links) and feeds
the path to the scorer. This preserves the exact production scoring
behaviour at the cost of a little extra IO per query.

Answer extraction
-----------------
When ``answer.method == "claude_cli"``, the adapter composes a short
prompt containing the retrieved context and the question, and invokes
``claude -p`` via ``subprocess.run``. No Anthropic SDK / ANTHROPIC_API_KEY
is required; the Claude Code CLI handles auth. On subprocess failure
(non-zero exit / timeout / binary missing) the adapter falls back to
returning the concatenated retrieved context as the "answer" and logs
the failure for the runner to surface.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make ``src`` importable when running ``python -m benchmarks.harness.runner``
# from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from src.memory.vector_store import VectorStore  # type: ignore
except Exception as e:  # pragma: no cover - import guard
    VectorStore = None  # type: ignore
    _IMPORT_ERROR: Optional[Exception] = e
else:
    _IMPORT_ERROR = None

try:
    from src.memory.scorer import MemoryScorer  # type: ignore
except Exception:  # pragma: no cover - import guard
    MemoryScorer = None  # type: ignore


DEFAULT_PERSIST_ROOT = _REPO_ROOT / "benchmarks" / "results" / "_chroma_sandbox"

logger = logging.getLogger("benchmarks.adapter")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class QAItem:
    question: str
    answer: str
    category: str = "unknown"
    evidence: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoCoMoSample:
    sample_id: str
    sessions: Dict[str, List[Dict[str, Any]]]  # session_name -> list of turns
    session_dates: Dict[str, str]              # session_name -> ISO date
    qa: List[QAItem]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "LoCoMoSample":
        """Best-effort parser for the upstream LoCoMo JSON shape."""
        conv = raw.get("conversation") or raw.get("sessions") or {}
        sessions: Dict[str, List[Dict[str, Any]]] = {}
        session_dates: Dict[str, str] = {}
        for key, val in conv.items():
            if key.endswith("_date_time") or key.endswith("_date"):
                base = key.rsplit("_date", 1)[0]
                session_dates[base] = str(val)
            elif isinstance(val, list):
                sessions[key] = val

        qa_raw = raw.get("qa") or raw.get("qa_pairs") or []
        qa: List[QAItem] = []
        for item in qa_raw:
            qa.append(
                QAItem(
                    question=str(item.get("question", "")),
                    answer=str(item.get("answer", "")),
                    category=_normalise_category(item.get("category")),
                    evidence=list(item.get("evidence", []) or []),
                    raw=item,
                )
            )

        sample_id = str(
            raw.get("sample_id")
            or raw.get("conv_id")
            or raw.get("id")
            or f"unknown-{uuid.uuid4().hex[:8]}"
        )
        return cls(
            sample_id=sample_id,
            sessions=sessions,
            session_dates=session_dates,
            qa=qa,
            raw=raw,
        )


_CATEGORY_MAP = {
    1: "single_hop",
    2: "multi_hop",
    3: "temporal",
    4: "open_domain",
    5: "adversarial",
}


def _normalise_category(value: Any) -> str:
    if isinstance(value, int) and value in _CATEGORY_MAP:
        return _CATEGORY_MAP[value]
    if isinstance(value, str) and value.strip():
        return value.strip().lower().replace("-", "_").replace(" ", "_")
    return "unknown"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class LoCoMoAdapter:
    """Inject LoCoMo samples into isolated lis-code-agent memory stores."""

    def __init__(
        self,
        persist_root: Path = DEFAULT_PERSIST_ROOT,
        collection: str = "conversations",
        top_k: int = 5,
    ):
        if VectorStore is None:  # pragma: no cover - import guard
            raise RuntimeError(
                f"Failed to import src.memory.vector_store: {_IMPORT_ERROR!r}"
            )
        self.persist_root = Path(persist_root)
        self.persist_root.mkdir(parents=True, exist_ok=True)
        self.collection = collection
        self.top_k = top_k
        self._stores: Dict[str, "VectorStore"] = {}
        # Latest-session date per sample, used as "today" for scorer rerank.
        self._reference_dates: Dict[str, date] = {}
        # Count of claude CLI failures per session (exposed for the runner).
        self.cli_failures = 0
        self.cli_calls = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare_memory(self, sample: LoCoMoSample) -> str:
        """Inject *sample*'s sessions into a fresh per-sample memory store."""
        session_id = f"locomo-{sample.sample_id}"
        store = self._make_store(session_id)

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        latest_date: Optional[date] = None

        for session_name, turns in sample.sessions.items():
            date_str = sample.session_dates.get(session_name, "")
            turn_date = _parse_iso_date(date_str)
            if turn_date is not None and (latest_date is None or turn_date > latest_date):
                latest_date = turn_date
            for i, turn in enumerate(turns):
                speaker = str(turn.get("speaker", "?"))
                text = str(turn.get("text", "")).strip()
                if not text:
                    continue
                doc = f"[{session_name}] [{date_str}] {speaker}: {text}"
                documents.append(doc)
                metadatas.append(
                    {
                        "sample_id": sample.sample_id,
                        "session_name": session_name,
                        "session_date": date_str,
                        "turn_index": i,
                        "speaker": speaker,
                        "dia_id": str(turn.get("dia_id", "")),
                        # Default relevance_score so retrieve_relevant_knowledge
                        # fusion matches the agent's production path.
                        "relevance_score": 1.0,
                    }
                )
                ids.append(f"{sample.sample_id}::{session_name}::{i}")

        if documents:
            store.add(
                collection=self.collection,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        # Reference date for scorer recency; fallback to today if the
        # sample has no parseable session dates.
        self._reference_dates[session_id] = latest_date or date.today()
        return session_id

    def query(
        self,
        session_id: str,
        question: str,
        config: Optional[Dict[str, Any]] = None,
        n_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve + (optional) rerank + answer.

        ``config`` is the loaded YAML config dict (see
        ``benchmarks/configs/v0_baseline_A.yaml``). When ``config`` is
        ``None`` or missing the relevant keys, falls back to the legacy
        raw-vector concat behaviour so old callers keep working.
        """
        store = self._stores.get(session_id)
        if store is None:
            raise KeyError(
                f"Unknown session_id {session_id!r}. Call prepare_memory first."
            )

        config = config or {}
        retrieval_cfg = config.get("retrieval") or {}
        rerank_cfg = config.get("rerank") or {}
        answer_cfg = config.get("answer") or {}
        memory_cfg = config.get("memory") or {}

        retrieval_api = (retrieval_cfg.get("api") or "raw_vector").strip()
        top_k = int(memory_cfg.get("top_k", n_results if n_results is not None else self.top_k))

        # 1. Retrieve.
        if retrieval_api == "retrieve_relevant_knowledge":
            hits = self._retrieve_relevant_knowledge(store, question, n_results=top_k)
        else:
            hits = self._retrieve_raw_vector(store, question, n_results=top_k)

        rerank_notes: List[str] = []

        # 2. Rerank (optional).
        if rerank_cfg.get("enabled"):
            method = (rerank_cfg.get("method") or "scorer_formula").strip()
            final_k = int(rerank_cfg.get("final_k", 5))
            if method == "scorer_formula" and hits:
                try:
                    hits = self._rerank_with_scorer(
                        hits,
                        reference_date=self._reference_dates.get(session_id, date.today()),
                        final_k=final_k,
                    )
                except Exception as e:
                    # Do NOT silently degrade — record it so the run report
                    # surfaces the regression.
                    rerank_notes.append(f"scorer_rerank_failed: {e!r}")
                    logger.warning("scorer rerank failed: %r", e)
                    hits = hits[:final_k]
            else:
                hits = hits[:final_k]

        # 3. Answer.
        answer_method = (answer_cfg.get("method") or "concat").strip()
        answer_text = ""
        cli_error: Optional[str] = None

        if answer_method == "claude_cli":
            model = str(answer_cfg.get("model") or "claude-sonnet-4-6")
            timeout = int(answer_cfg.get("timeout", 60))
            answer_text, cli_error = self._answer_via_claude_cli(
                question=question,
                hits=hits,
                model=model,
                timeout=timeout,
            )
            if cli_error:
                # Fall back to concat so the pipeline still produces SOMETHING.
                answer_text = _concat_answer(hits)
        else:
            answer_text = _concat_answer(hits)

        return {
            "answer": answer_text,
            "retrieved": hits,
            "n_retrieved": len(hits),
            "cli_error": cli_error,
            "rerank_notes": rerank_notes,
        }

    def cleanup(self, session_id: str) -> None:
        """Drop the per-sample Chroma directory. Safe to call repeatedly."""
        store = self._stores.pop(session_id, None)
        self._reference_dates.pop(session_id, None)
        del store
        sample_dir = self.persist_root / session_id
        if sample_dir.exists():
            shutil.rmtree(sample_dir, ignore_errors=True)

    def cleanup_all(self) -> None:
        for sid in list(self._stores.keys()):
            self.cleanup(sid)

    # ------------------------------------------------------------------
    # Retrieval strategies
    # ------------------------------------------------------------------

    def _retrieve_raw_vector(
        self,
        store: "VectorStore",
        question: str,
        n_results: int,
    ) -> List[Dict[str, Any]]:
        """Legacy path: raw nearest-neighbour."""
        raw_hits = store.search(
            query=question,
            collection=self.collection,
            n_results=n_results,
        )
        # Normalise shape to match _retrieve_relevant_knowledge output.
        normalised = []
        for h in raw_hits:
            distance = h.get("distance", 1.0)
            md = h.get("metadata", {}) or {}
            relevance = md.get("relevance_score", 1.0)
            combined = (1.0 / (1.0 + distance)) * relevance
            normalised.append(
                {
                    "text": h.get("document", ""),
                    "metadata": md,
                    "distance": distance,
                    "relevance_score": relevance,
                    "combined_score": combined,
                }
            )
        return normalised

    def _retrieve_relevant_knowledge(
        self,
        store: "VectorStore",
        question: str,
        n_results: int,
    ) -> List[Dict[str, Any]]:
        """Mirror of ``src/memory/indexer.py::retrieve_relevant_knowledge``
        but run against the sandbox's ``conversations`` collection.

        The production function is hard-coded to read the ``knowledge``
        collection. The benchmark sandbox populates ``conversations`` so
        the adapter replicates the same distance+relevance fusion here.
        The formula matches the production one exactly, so upstream
        tweaks in indexer.py should be mirrored here if we keep this
        benchmark meaningful.
        """
        collection = store.client.get_or_create_collection(name=self.collection)
        if collection.count() == 0:
            return []

        query_embedding = store._embed([question])
        fetch_n = min(max(n_results * 2, 1), collection.count())
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=fetch_n,
        )

        docs = (results.get("documents") or [[]])[0]
        if not docs:
            return []
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[1.0] * len(docs)])[0]

        ranked: List[Dict[str, Any]] = []
        for i, doc in enumerate(docs):
            md = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            relevance = md.get("relevance_score", 1.0)
            combined = (1.0 / (1.0 + distance)) * relevance
            ranked.append(
                {
                    "text": doc,
                    "metadata": md,
                    "distance": distance,
                    "relevance_score": relevance,
                    "combined_score": combined,
                }
            )

        ranked.sort(key=lambda h: h["combined_score"], reverse=True)
        return ranked[:n_results]

    # ------------------------------------------------------------------
    # Rerank
    # ------------------------------------------------------------------

    def _rerank_with_scorer(
        self,
        hits: List[Dict[str, Any]],
        reference_date: date,
        final_k: int,
    ) -> List[Dict[str, Any]]:
        """Re-rank hits by calling the real MemoryScorer.score_file.

        Strategy: write each hit to a temp .md file whose YAML frontmatter
        carries synthetic fields the scorer consumes (base_weight, updated,
        links, id). This lets us reuse the production formula verbatim
        instead of re-implementing it. The temp directory is cleaned up
        on return.

        The mapping from retrieval hit to frontmatter fields:
          - base_weight = combined_score (distance+relevance fusion)
                          clamped to scorer's valid range [0.6, 1.0].
          - updated     = session_date parsed from metadata; scorer
                          applies exp(-days_since / 30) decay against
                          ``reference_date`` (the sample's last session).
          - links       = [] (no cross-references in a single-sample
                          retrieval batch, so reference_boost = 1.0).
          - id          = stable-ish id derived from metadata.
        """
        if MemoryScorer is None:
            raise RuntimeError("MemoryScorer import failed; rerank unavailable.")

        scorer = MemoryScorer()
        with tempfile.TemporaryDirectory(prefix="locomo_rerank_") as tmpdir:
            tmp_root = Path(tmpdir)
            scored_pairs: List[tuple[float, Dict[str, Any]]] = []
            for idx, hit in enumerate(hits):
                md = hit.get("metadata", {}) or {}
                base_weight = max(0.6, min(1.0, float(hit.get("combined_score", 0.9))))
                updated_date = _parse_iso_date(str(md.get("session_date", ""))) or reference_date
                fm = {
                    "id": f"hit_{idx}",
                    "type": "stm",
                    "category": "technical",
                    "status": "active",
                    "base_weight": base_weight,
                    "updated": updated_date.isoformat(),
                    "links": [],
                    "summary": "retrieval hit",
                }
                path = tmp_root / f"hit_{idx}.md"
                _write_frontmatter_file(path, fm, body=hit.get("text", ""))
                scored = scorer.score_file(
                    path=path,
                    today=reference_date,
                    all_files=None,  # no cross-links in this batch
                )
                # Blend scorer.score into the retrieval combined_score so
                # the final ordering reflects both similarity and recency.
                rerank_score = float(scored.score) * float(hit.get("combined_score", 1.0))
                hit = dict(hit)
                hit["rerank_score"] = rerank_score
                hit["scorer_score"] = float(scored.score)
                scored_pairs.append((rerank_score, hit))

        scored_pairs.sort(key=lambda p: p[0], reverse=True)
        return [h for _, h in scored_pairs[:final_k]]

    # ------------------------------------------------------------------
    # Answer extraction via `claude -p`
    # ------------------------------------------------------------------

    def _answer_via_claude_cli(
        self,
        question: str,
        hits: List[Dict[str, Any]],
        model: str,
        timeout: int,
    ) -> tuple[str, Optional[str]]:
        """Invoke ``claude -p`` as a subprocess; returns (answer, error_or_None).

        Deliberately does NOT pass ``--allowedTools`` — we want a pure
        text completion with no tool calls. The prompt is kept short and
        opinionated (one factual sentence) so BLEU/F1/ROUGE-L scores
        against LoCoMo's terse gold answers are meaningful.
        """
        self.cli_calls += 1
        cli_path = shutil.which("claude")
        if not cli_path:
            self.cli_failures += 1
            return "", "claude CLI not found on PATH"

        prompt = _build_prompt(question=question, hits=hits)
        try:
            completed = subprocess.run(
                [cli_path, "-p", prompt, "--model", model],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.cli_failures += 1
            return "", f"claude CLI timed out after {timeout}s"
        except Exception as e:  # pragma: no cover - unexpected
            self.cli_failures += 1
            return "", f"claude CLI raised: {e!r}"

        if completed.returncode != 0:
            self.cli_failures += 1
            stderr_tail = (completed.stderr or "").strip().splitlines()[-3:]
            return "", (
                f"claude CLI exit {completed.returncode}; "
                f"stderr: {' | '.join(stderr_tail)}"
            )

        out = (completed.stdout or "").strip()
        if not out:
            # Treat empty stdout as failure so we fall back to concat.
            self.cli_failures += 1
            return "", "claude CLI returned empty stdout"
        return out, None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_store(self, session_id: str) -> "VectorStore":
        persist_path = self.persist_root / session_id / "chroma"
        store = VectorStore(persist_path=str(persist_path))  # type: ignore[arg-type]
        self._stores[session_id] = store
        return store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso_date(value: str) -> Optional[date]:
    """Parse LoCoMo's session_date ('YYYY-MM-DD HH:MM' or similar) to a date."""
    if not value:
        return None
    # LoCoMo dates are occasionally like "1:56 pm on 8 May, 2023" — we take
    # a defensive approach and try the common shapes, then give up.
    head = value.strip().split("T", 1)[0].split(" ", 1)[0]
    try:
        return date.fromisoformat(head)
    except ValueError:
        pass
    # Fallback: pull the first YYYY-MM-DD pattern.
    import re as _re
    m = _re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _write_frontmatter_file(path: Path, meta: Dict[str, Any], body: str = "") -> None:
    """Write a minimal YAML-frontmatter MD for the scorer to consume."""
    import yaml  # MemoryManager already requires pyyaml, so this import is safe.

    yaml_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()
    path.write_text(f"---\n{yaml_str}\n---\n{body}\n", encoding="utf-8")


def _concat_answer(hits: List[Dict[str, Any]]) -> str:
    return " | ".join(h.get("text", "") for h in hits if h.get("text"))


def _format_context(hits: List[Dict[str, Any]]) -> str:
    """Render hits as ``[id|date|speaker] text`` lines for the LLM prompt."""
    lines = []
    for h in hits:
        md = h.get("metadata", {}) or {}
        date_str = str(md.get("session_date", "")).strip() or "?"
        speaker = str(md.get("speaker", "?")).strip() or "?"
        session = str(md.get("session_name", "")).strip() or "?"
        turn_idx = md.get("turn_index", "?")
        id_label = f"{session}#{turn_idx}"
        text = h.get("text", "").strip()
        lines.append(f"[{id_label}|{date_str}|{speaker}] {text}")
    return "\n".join(lines)


def _build_prompt(question: str, hits: List[Dict[str, Any]]) -> str:
    context = _format_context(hits) or "(no context retrieved)"
    return (
        "Based on the following memory, answer the question concisely "
        "(one short sentence, factual only).\n\n"
        f"MEMORY:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
    )


# ---------------------------------------------------------------------------
# Convenience loaders
# ---------------------------------------------------------------------------


def load_samples(path: Path) -> List[LoCoMoSample]:
    """Load a LoCoMo JSON file into a list of ``LoCoMoSample``."""
    import json

    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "samples" in data:
        items = data["samples"]
    elif isinstance(data, list):
        items = data
    else:
        items = list(data.values()) if isinstance(data, dict) else []
    return [LoCoMoSample.from_raw(item) for item in items if isinstance(item, dict)]

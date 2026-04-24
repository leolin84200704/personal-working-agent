"""LoCoMo -> lis-code-agent memory adapter.

Responsibilities
----------------
1. Load a LoCoMo sample (one long multi-session dialogue + QA pairs).
2. Inject that dialogue into an **isolated** lis-code-agent memory store so
   that different samples do not pollute each other.
3. Expose ``prepare_memory(sample) -> session_id`` and
   ``query(session_id, question) -> answer`` so the runner is decoupled
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

The actual store API calls are the documented ones on
``src.memory.vector_store.VectorStore`` (see module docstring there):
``vs.add(collection, documents, metadatas, ids)`` and
``vs.search(query, collection, n_results)``.

# TODO: verify API — if a future refactor gives ``manager.py`` a unified
# ``retrieve(query)`` entrypoint, update ``query()`` to call that instead
# of the raw vector store, so we benchmark the full retrieval pipeline
# (scoring, re-ranking, tier routing) rather than just nearest-neighbour.
"""
from __future__ import annotations

import shutil
import sys
import uuid
from dataclasses import dataclass, field
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


DEFAULT_PERSIST_ROOT = _REPO_ROOT / "benchmarks" / "results" / "_chroma_sandbox"


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
        """Best-effort parser for the upstream LoCoMo JSON shape.

        LoCoMo's published shape is roughly::

            {
              "sample_id": "...",
              "conversation": {
                "session_1": [{"speaker": "...", "text": "..."}],
                "session_1_date_time": "YYYY-MM-DD HH:MM",
                "session_2": [...],
                ...
              },
              "qa": [{"question": "...", "answer": "...", "category": 1}]
            }

        # TODO: verify API — after the first real download, adjust the
        # field names / category mapping to match exactly what we got.
        """
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare_memory(self, sample: LoCoMoSample) -> str:
        """Inject *sample*'s sessions into a fresh per-sample memory store.

        Returns a ``session_id`` the runner passes back to ``query``.
        """
        session_id = f"locomo-{sample.sample_id}"
        store = self._make_store(session_id)

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        for session_name, turns in sample.sessions.items():
            date = sample.session_dates.get(session_name, "")
            # One document per turn keeps retrieval granular; alternative
            # would be one doc per session. We go with per-turn here so
            # multi-hop / temporal questions can find the exact line.
            for i, turn in enumerate(turns):
                speaker = str(turn.get("speaker", "?"))
                text = str(turn.get("text", "")).strip()
                if not text:
                    continue
                doc = f"[{session_name}] [{date}] {speaker}: {text}"
                documents.append(doc)
                metadatas.append(
                    {
                        "sample_id": sample.sample_id,
                        "session_name": session_name,
                        "session_date": date,
                        "turn_index": i,
                        "speaker": speaker,
                        "dia_id": str(turn.get("dia_id", "")),
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
        return session_id

    def query(
        self,
        session_id: str,
        question: str,
        n_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return a pseudo-answer + retrieved context for *question*.

        v0 baseline: we do not invoke the real agent loop (that would
        require the Anthropic API). Instead we return the top-k retrieved
        conversation turns as "evidence" and a stitched-together string as
        the ``answer``. The judge module scores this against the gold
        answer. When v1 wires in the actual agent, ``query`` will call
        into it and return the agent's free-form answer verbatim.

        # TODO: verify API — swap this for a proper agent call that uses
        # ``MemoryManager`` + system prompt once Leo decides on the v0
        # question-answering path (LLM call vs retrieval-only baseline).
        """
        store = self._stores.get(session_id)
        if store is None:
            raise KeyError(
                f"Unknown session_id {session_id!r}. Call prepare_memory first."
            )

        k = n_results if n_results is not None else self.top_k
        hits = store.search(
            query=question,
            collection=self.collection,
            n_results=k,
        )
        retrieved_texts = [h.get("document", "") for h in hits]
        # Naive "answer": concat top-k. Real v0 would feed these through a
        # tiny LLM call. We keep it offline for skeleton verification.
        answer = " | ".join(retrieved_texts) if retrieved_texts else ""
        return {
            "answer": answer,
            "retrieved": hits,
            "n_retrieved": len(hits),
        }

    def cleanup(self, session_id: str) -> None:
        """Drop the per-sample Chroma directory. Safe to call repeatedly."""
        store = self._stores.pop(session_id, None)
        # Let Chroma release file handles by dropping the reference.
        del store
        sample_dir = self.persist_root / session_id
        if sample_dir.exists():
            shutil.rmtree(sample_dir, ignore_errors=True)

    def cleanup_all(self) -> None:
        for sid in list(self._stores.keys()):
            self.cleanup(sid)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_store(self, session_id: str) -> "VectorStore":
        persist_path = self.persist_root / session_id / "chroma"
        # Each VectorStore maintains its own Chroma client rooted here.
        store = VectorStore(persist_path=str(persist_path))  # type: ignore[arg-type]
        self._stores[session_id] = store
        return store


# ---------------------------------------------------------------------------
# Convenience loaders
# ---------------------------------------------------------------------------


def load_samples(path: Path) -> List[LoCoMoSample]:
    """Load a LoCoMo JSON file into a list of ``LoCoMoSample``.

    Handles both ``[sample, sample, ...]`` and ``{"samples": [...]}`` shapes.
    """
    import json

    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "samples" in data:
        items = data["samples"]
    elif isinstance(data, list):
        items = data
    else:
        # Some upstream versions store a single dict of dicts keyed by id.
        items = list(data.values()) if isinstance(data, dict) else []
    return [LoCoMoSample.from_raw(item) for item in items if isinstance(item, dict)]

"""
Memory Indexer - Parse MD files into ChromaDB for semantic retrieval.

Parses MEMORY.md and SOUL.md (detailed sections) into individual entries,
each stored as a vector with metadata for Tier 2 retrieval.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.memory.vector_store import VectorStore

settings = get_settings()

# Collection name for indexed knowledge
KNOWLEDGE_COLLECTION = "knowledge"


def _parse_sections(content: str, min_length: int = 50) -> list[dict[str, Any]]:
    """
    Parse markdown content into sections by ### headers.

    Returns a list of dicts with:
      - id: hash of content for dedup
      - text: the section content
      - title: the section header
      - parent: the ## parent header (if any)
    """
    sections = []
    current_h2 = ""
    current_h3 = ""
    current_lines: list[str] = []

    def flush():
        if current_lines:
            text = "\n".join(current_lines).strip()
            if len(text) >= min_length:
                content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
                sections.append({
                    "id": f"kb_{content_hash}",
                    "text": text,
                    "title": current_h3 or current_h2 or "untitled",
                    "parent": current_h2,
                })

    for line in content.split("\n"):
        stripped = line.strip()

        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush()
            current_h2 = stripped[3:].strip()
            current_h3 = ""
            current_lines = []
        elif stripped.startswith("### "):
            flush()
            current_h3 = stripped[4:].strip()
            current_lines = [line]
        elif stripped.startswith("#### "):
            # Include as part of current section, don't split
            current_lines.append(line)
        else:
            current_lines.append(line)

    flush()
    return sections


def index_memory_file(vector_store: VectorStore, agent_root: Path | None = None) -> int:
    """
    Index MEMORY.md sections into ChromaDB.

    Returns the number of sections indexed.
    """
    if agent_root is None:
        agent_root = settings.agent_root

    memory_path = agent_root / "MEMORY.md"
    if not memory_path.exists():
        return 0

    content = memory_path.read_text(encoding="utf-8")
    sections = _parse_sections(content)

    if not sections:
        return 0

    # Ensure collection exists
    collection = vector_store.client.get_or_create_collection(
        name=KNOWLEDGE_COLLECTION,
        metadata={"description": "Indexed knowledge from MD files"},
    )

    # Clear existing entries from this source
    try:
        existing = collection.get(where={"source": "MEMORY.md"})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    # Add sections
    documents = []
    metadatas = []
    ids = []

    for section in sections:
        documents.append(section["text"])
        metadatas.append({
            "source": "MEMORY.md",
            "title": section["title"],
            "parent": section["parent"],
            "relevance_score": 1.0,  # Default score, adjustable by feedback
        })
        ids.append(section["id"])

    embeddings = vector_store._embed(documents)
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
        embeddings=embeddings,
    )

    return len(sections)


def index_soul_details(vector_store: VectorStore, agent_root: Path | None = None) -> int:
    """
    Index SOUL.md detailed sections (examples, failure cases) into ChromaDB.
    These are Tier 2 — not always loaded, retrieved when relevant.

    The core rules are in SOUL_CORE.md (Tier 1, always loaded).
    """
    if agent_root is None:
        agent_root = settings.agent_root

    soul_path = agent_root / "SOUL.md"
    if not soul_path.exists():
        return 0

    content = soul_path.read_text(encoding="utf-8")
    sections = _parse_sections(content)

    if not sections:
        return 0

    collection = vector_store.client.get_or_create_collection(
        name=KNOWLEDGE_COLLECTION,
        metadata={"description": "Indexed knowledge from MD files"},
    )

    # Clear existing entries from this source
    try:
        existing = collection.get(where={"source": "SOUL.md"})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    documents = []
    metadatas = []
    ids = []

    for section in sections:
        documents.append(section["text"])
        metadatas.append({
            "source": "SOUL.md",
            "title": section["title"],
            "parent": section["parent"],
            "relevance_score": 1.0,
        })
        ids.append(f"soul_{section['id']}")

    embeddings = vector_store._embed(documents)
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
        embeddings=embeddings,
    )

    return len(sections)


def retrieve_relevant_knowledge(
    vector_store: VectorStore,
    query: str,
    n_results: int = 5,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Retrieve knowledge sections relevant to a query.

    Combines vector similarity with relevance_score metadata.
    Returns sections sorted by combined score.
    """
    collection = vector_store.client.get_or_create_collection(
        name=KNOWLEDGE_COLLECTION,
    )

    if collection.count() == 0:
        return []

    query_embedding = vector_store._embed([query])

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(n_results * 2, collection.count()),  # Fetch more, then filter/rank
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    # Combine vector distance with relevance_score
    ranked = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results.get("distances") else 1.0

        # Lower distance = more similar. relevance_score is 0-2 range.
        relevance = metadata.get("relevance_score", 1.0)
        # Combined score: similarity (inverted distance) * relevance weight
        combined = (1.0 / (1.0 + distance)) * relevance

        if combined >= min_score:
            ranked.append({
                "text": doc,
                "title": metadata.get("title", ""),
                "parent": metadata.get("parent", ""),
                "source": metadata.get("source", ""),
                "distance": distance,
                "relevance_score": relevance,
                "combined_score": combined,
            })

    # Sort by combined score descending
    ranked.sort(key=lambda x: x["combined_score"], reverse=True)

    return ranked[:n_results]


def update_relevance_score(
    vector_store: VectorStore,
    query: str,
    delta: float,
) -> int:
    """
    Update relevance_score for knowledge entries matching a query.

    Positive delta = knowledge was useful (user accepted).
    Negative delta = knowledge was not useful (user corrected).

    Returns the number of entries updated.
    """
    collection = vector_store.client.get_or_create_collection(
        name=KNOWLEDGE_COLLECTION,
    )

    if collection.count() == 0:
        return 0

    query_embedding = vector_store._embed([query])
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=3,
    )

    if not results["ids"] or not results["ids"][0]:
        return 0

    updated = 0
    for i, doc_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        current_score = metadata.get("relevance_score", 1.0)
        new_score = max(0.1, min(2.0, current_score + delta))  # Clamp to [0.1, 2.0]

        metadata["relevance_score"] = new_score
        collection.update(
            ids=[doc_id],
            metadatas=[metadata],
        )
        updated += 1

    return updated

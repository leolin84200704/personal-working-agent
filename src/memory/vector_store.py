"""
Vector Store - ChromaDB integration for semantic memory retrieval.

Provides RAG (Retrieval Augmented Generation) capabilities
for finding relevant past conversations and patterns.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Try to import chromadb, handle gracefully if not installed
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

# Try to import sentence_transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None


class VectorStore:
    """
    Vector database for semantic memory retrieval.

    Uses ChromaDB for storage and sentence-transformers for embeddings.
    """

    def __init__(self, persist_path: str = "./storage/chroma"):
        """Initialize the vector store."""
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is not installed. "
                "Install it with: pip install chromadb"
            )

        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_path),
        )

        # Initialize embedding function
        self.embedding_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                print(f"Warning: Could not load embedding model: {e}")

        # Get or create collections
        self.conversations = self._get_collection("conversations")
        self.patterns = self._get_collection("patterns")
        self.gotchas = self._get_collection("gotchas")
        self.code_snippets = self._get_collection("code_snippets")

    def _get_collection(self, name: str):
        """Get or create a collection."""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"description": f"{name} collection"}
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts."""
        if self.embedding_model is not None:
            return self.embedding_model.encode(texts).tolist()
        # Fallback: ChromaDB will use default embedding
        return None

    def add(
        self,
        collection: str,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """
        Add documents to a collection.

        Args:
            collection: Name of the collection
            documents: List of document texts
            metadatas: Optional list of metadata dicts
            ids: Optional list of unique IDs
        """
        coll = getattr(self, collection, None)
        if coll is None:
            raise ValueError(f"Collection not found: {collection}")

        # Generate embeddings
        embeddings = self._embed(documents)

        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]

        coll.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas or [{}] * len(documents),
            ids=ids,
        )

    def search(
        self,
        query: str,
        collection: str = "conversations",
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query: Search query text
            collection: Name of the collection to search
            n_results: Number of results to return

        Returns:
            List of dicts with document, metadata, and distance
        """
        coll = getattr(self, collection, None)
        if coll is None:
            raise ValueError(f"Collection not found: {collection}")

        # Embed query
        query_embedding = self._embed([query])

        # Search
        results = coll.query(
            query_embeddings=query_embedding,
            n_results=n_results,
        )

        # Format results
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "document": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })

        return formatted

    def get(
        self,
        collection: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get documents from a collection.

        Args:
            collection: Name of the collection
            ids: Optional list of document IDs
            where: Optional metadata filter

        Returns:
            List of dicts with document and metadata
        """
        coll = getattr(self, collection, None)
        if coll is None:
            raise ValueError(f"Collection not found: {collection}")

        results = coll.get(ids=ids, where=where)

        formatted = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"]):
                formatted.append({
                    "id": results["ids"][i] if results["ids"] else None,
                    "document": doc,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })

        return formatted

    def delete(
        self,
        collection: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> None:
        """
        Delete documents from a collection.

        Args:
            collection: Name of the collection
            ids: Optional list of document IDs to delete
            where: Optional metadata filter
        """
        coll = getattr(self, collection, None)
        if coll is None:
            raise ValueError(f"Collection not found: {collection}")

        coll.delete(ids=ids, where=where)

    def clear(self, collection: str) -> None:
        """Clear all documents from a collection."""
        # Delete and recreate the collection
        self.client.delete_collection(collection)
        setattr(self, collection, self._get_collection(collection))

    def stats(self) -> dict[str, int]:
        """Get statistics about all collections."""
        return {
            "conversations": self.conversations.count(),
            "patterns": self.patterns.count(),
            "gotchas": self.gotchas.count(),
            "code_snippets": self.code_snippets.count(),
        }


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store(persist_path: str = "./storage/chroma") -> VectorStore:
    """Get the global VectorStore instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(persist_path=persist_path)
    return _vector_store

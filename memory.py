"""SurpriseSage — ChromaDB RAG memory layer."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

import config

logger = logging.getLogger("surprisesage.memory")


class MemoryStore:
    """Persistent vector memory backed by ChromaDB + Ollama embeddings."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        db_path = str(config.APP_DIR / f"surprisesage_memory_{user_id}")

        self._client = chromadb.PersistentClient(path=db_path)
        self._ef = OllamaEmbeddingFunction(
            model_name=config.EMBED_MODEL,
            url=config.OLLAMA_BASE_URL,
        )
        self._collection = self._client.get_or_create_collection(
            name="memories",
            embedding_function=self._ef,
        )
        logger.info("✅ MemoryStore initialized for user '%s' at %s", user_id, db_path)

    # ── Write ────────────────────────────────────────────────────────────

    def save_memory(
        self,
        text: str,
        category: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a document to memory. Returns the generated ID."""
        doc_id = uuid.uuid4().hex

        meta = {
            "category": category,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            meta.update(metadata)

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[text],
                metadatas=[meta],
            )
            logger.debug("Saved memory [%s] | category=%s", doc_id[:8], category)
        except Exception:
            logger.exception("Failed to save memory")

        return doc_id

    def save_feedback(
        self, surprise_id: str, score: int, surprise_text: str
    ) -> None:
        """Save user feedback (+1 or -1) linked to a surprise."""
        self.save_memory(
            text=surprise_text,
            category="feedback",
            metadata={
                "surprise_id": surprise_id,
                "feedback_score": score,
            },
        )
        logger.info("Feedback saved: surprise=%s score=%+d", surprise_id[:8], score)

    # ── Read ─────────────────────────────────────────────────────────────

    def get_relevant_memories(
        self,
        query: str,
        n_results: int | None = None,
        category_filter: str | None = None,
    ) -> List[Dict]:
        """Query the memory store. Returns list of {text, metadata, distance}."""
        if n_results is None:
            n_results = config.MAX_MEMORY_RESULTS

        try:
            where = {"category": category_filter} if category_filter else None

            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
        except Exception:
            logger.exception("Failed to query memories")
            return []

        memories = []
        if results and results.get("documents"):
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                memories.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                })
        return memories

    # ── Cleanup ──────────────────────────────────────────────────────────

    def run_cleanup(self, retention_days: int | None = None) -> int:
        """Delete memories older than retention_days. Returns count deleted."""
        if retention_days is None:
            retention_days = config.MEMORY_RETENTION_DAYS

        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()

        try:
            all_data = self._collection.get(include=["metadatas"])
            to_delete = [
                doc_id
                for doc_id, meta in zip(all_data["ids"], all_data["metadatas"])
                if meta.get("timestamp", "") < cutoff
            ]

            if to_delete:
                self._collection.delete(ids=to_delete)
                logger.info("🧹 Cleaned up %d old memories", len(to_delete))
            else:
                logger.debug("Cleanup ran — no old memories to delete")

            return len(to_delete)

        except Exception:
            logger.exception("Memory cleanup failed")
            return 0

    # ── Utility ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return basic stats about the memory store."""
        try:
            total = self._collection.count()
            return {
                "total_memories": total,
                "user_id": self.user_id,
                "db_path": str(config.APP_DIR / f"surprisesage_memory_{self.user_id}"),
            }
        except Exception:
            return {"total_memories": 0, "error": "Failed to get stats"}

    def clear_all(self) -> int:
        """⚠️ DANGER: Delete ALL memories. Returns count deleted."""
        try:
            count = self._collection.count()
            self._collection.delete(where={})
            logger.warning("🗑️ Cleared ALL %d memories", count)
            return count
        except Exception:
            logger.exception("Failed to clear memory")
            return 0


# ── Quick debug when running the file directly ───────────────────────────
if __name__ == "__main__":
    profile = config.load_profile()
    memory = MemoryStore(profile["user_id"])
    stats = memory.get_stats()

    print("🧠 SurpriseSage Memory Store")
    print("=" * 40)
    print(f"User ID      : {stats['user_id']}")
    print(f"Total memories: {stats['total_memories']}")
    print(f"DB location  : {stats['db_path']}")
    print()

    # Show last 5 memories
    recent = memory.get_relevant_memories("general wisdom", n_results=5)
    if recent:
        print("Last 5 memories:")
        for i, mem in enumerate(recent, 1):
            print(f"{i:2d}. {mem['text'][:80]}...")
    else:
        print("No memories yet.")
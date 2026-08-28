import logging
from typing import Any, Dict, List, Optional

from config import settings

try:
    from qdrant_client import QdrantClient, models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

CONCEPTS_COLLECTION = "concepts"
CHUNKS_COLLECTION = "chunks"


class VectorStore:
    """
    Qdrant wrapper with two collections.

    concepts — one point per canonical concept, for concept lookup and
               relationship questions.
    chunks   — one point per text chunk, so open questions whose answer lives
               in prose that concept extraction never captured are still
               answerable.

    Runs embedded from a local directory when no URL is configured. At this
    corpus size that is the sensible default: no server to run, no credentials,
    and the same API as a hosted instance.
    """

    def __init__(self, url: str = "", api_key: str = "", path: str = ""):
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.path = path or settings.qdrant_path
        self._client: Optional["QdrantClient"] = None

    def connect(self) -> "QdrantClient":
        if not QDRANT_AVAILABLE:
            raise RuntimeError("qdrant-client is not installed. Run: pip install qdrant-client")
        if self._client is None:
            if self.url:
                logging.info(f"Connecting to Qdrant at {self.url}")
                # The default timeout is a few seconds, which a cold free-tier
                # cloud cluster regularly exceeds on its first write.
                self._client = QdrantClient(
                    url=self.url,
                    api_key=self.api_key or None,
                    timeout=settings.qdrant_timeout,
                )
            else:
                logging.info(f"Using embedded Qdrant at ./{self.path}")
                self._client = QdrantClient(path=self.path)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def recreate(self, collection: str, dimension: int) -> None:
        client = self.connect()
        if client.collection_exists(collection):
            client.delete_collection(collection)
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )
        logging.info(f"Created collection '{collection}' (dim={dimension})")

    def upsert(self, collection: str, ids: List[int], vectors: List[List[float]],
               payloads: List[Dict[str, Any]]) -> int:
        client = self.connect()
        # Uploaded in batches: a single request carrying every 1024-dim vector
        # plus its payload is large enough to time out against a hosted cluster.
        size = settings.qdrant_upsert_batch
        for i in range(0, len(ids), size):
            client.upsert(
                collection_name=collection,
                points=models.Batch(
                    ids=ids[i:i + size],
                    vectors=vectors[i:i + size],
                    payloads=payloads[i:i + size],
                ),
                wait=True,
            )
        return len(ids)

    def search(self, collection: str, vector: List[float], limit: int = 10,
               score_threshold: float = 0.0) -> List[Dict[str, Any]]:
        client = self.connect()
        hits = client.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
            score_threshold=score_threshold or None,
            with_payload=True,
        ).points
        return [{"score": h.score, **(h.payload or {})} for h in hits]

    def count(self, collection: str) -> int:
        client = self.connect()
        if not client.collection_exists(collection):
            return 0
        return client.count(collection_name=collection).count

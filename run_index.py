import hashlib
import json
import logging
import os

from config import settings
from logging_setup import configure_logging
from retrieval.embedder import Embedder, concept_embedding_text
from retrieval.vector_store import VectorStore


def _point_id(s: str) -> int:
    # Qdrant point ids must be int or UUID; a stable hash of the domain id keeps
    # re-indexing idempotent without maintaining a separate counter.
    return int(hashlib.sha256(s.encode()).hexdigest()[:15], 16)


def main():
    configure_logging()

    CONCEPTS_FILE = os.path.join(settings.data_dir, "normalized_concepts.json")
    CHUNKS_FILE = os.path.join(settings.output_dir, "preprocessed_chunks.json")

    for path in (CONCEPTS_FILE, CHUNKS_FILE):
        if not os.path.exists(path):
            logging.error(f"Required input not found: {path}")
            raise FileNotFoundError(path)

    with open(CONCEPTS_FILE, encoding="utf-8") as f:
        concepts = json.load(f)["concepts"]
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)["chunks"]

    logging.info("ConceptScape Indexing starting...")
    logging.info(f"Concepts: {len(concepts)} | Chunks: {len(chunks)}")

    embedder = Embedder()
    store = VectorStore()

    try:
        dim = embedder.dimension

        # ── concepts ──────────────────────────────────────────────────────
        store.recreate(store.concepts_collection, dim)
        texts = [concept_embedding_text(c) for c in concepts]
        vectors = embedder.encode_documents(texts)
        store.upsert(
            store.concepts_collection,
            ids=[_point_id(c["concept_id"]) for c in concepts],
            vectors=vectors,
            payloads=[{
                "concept_id": c["concept_id"],
                "canonical_name": c.get("canonical_name", ""),
                "definition": c.get("definition", ""),
                "aliases": c.get("aliases", []),
                "keywords": c.get("keywords", []),
                "filenames": c.get("filenames", []),
                "page_numbers": c.get("page_numbers", []),
                "chunk_ids": c.get("chunk_ids", []),
                "evidence": c.get("evidence", []),
                "occurrence_count": c.get("occurrence_count", 0),
            } for c in concepts],
        )
        logging.info(f"Indexed {len(concepts)} concepts")

        # ── chunks ────────────────────────────────────────────────────────
        usable = [c for c in chunks if c.get("text", "").strip()]
        store.recreate(store.chunks_collection, dim)
        vectors = embedder.encode_documents([c["text"] for c in usable])
        store.upsert(
            store.chunks_collection,
            ids=[_point_id(c["chunk_id"]) for c in usable],
            vectors=vectors,
            payloads=[{
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "filename": c.get("filename", ""),
                "location_number": c.get("location_number", 0),
                "location_type": c.get("location_type", ""),
                "resource_id": c.get("resource_id", ""),
            } for c in usable],
        )
        logging.info(f"Indexed {len(usable)} chunks")

        logging.info("\n" + "=" * 50)
        logging.info("INDEXING COMPLETE")
        logging.info("=" * 50)
        logging.info(f"Model      : {settings.embedding_model} (dim={dim})")
        logging.info(f"Backend    : {settings.qdrant_url or 'embedded at ./' + settings.qdrant_path}")
        logging.info(f"concepts   : {store.count(store.concepts_collection)} points")
        logging.info(f"chunks     : {store.count(store.chunks_collection)} points")
    finally:
        store.close()


if __name__ == "__main__":
    main()

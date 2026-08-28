import json
import logging
import os
from collections import Counter
from dataclasses import asdict

from config import settings
from logging_setup import configure_logging
from relationships.extractor import RelationshipExtractor


def main():
    configure_logging()

    CHUNKS_FILE = os.path.join(settings.output_dir, "preprocessed_chunks.json")
    CONCEPTS_FILE = os.path.join(settings.data_dir, "normalized_concepts.json")
    OUTPUT_FILE = os.path.join(settings.data_dir, "relationships.json")

    for path in (CHUNKS_FILE, CONCEPTS_FILE):
        if not os.path.exists(path):
            logging.error(f"Required input not found: {path}")
            return

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    with open(CONCEPTS_FILE, "r", encoding="utf-8") as f:
        concepts_data = json.load(f)

    logging.info("ConceptScape Relationship Extraction starting...")
    logging.info(f"Concepts: {len(concepts_data.get('concepts', []))}")

    # Reuse previously extracted relationships for chunks whose text is unchanged,
    # so a quota-limited run resumes instead of paying for everything again.
    prev_rels, prev_processed = [], {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                prev = json.load(f)
            prev_rels = prev.get("relationships", [])
            prev_processed = prev.get("processed_chunks", {})
        except Exception:
            logging.warning("Could not read previous relationships.json — treating as full miss")

    chunk_hashes = {c["chunk_id"]: c.get("content_hash", "") for c in chunks_data.get("chunks", [])}
    cached_ids = {cid for cid, h in prev_processed.items() if chunk_hashes.get(cid) == h}
    if cached_ids:
        logging.info(f"CACHE: {len(cached_ids)} chunk(s) unchanged, reusing their relationships")
        chunks_data = {
            **chunks_data,
            "chunks": [c for c in chunks_data["chunks"] if c["chunk_id"] not in cached_ids],
        }

    extractor = RelationshipExtractor()
    result = extractor.process(chunks_data, concepts_data)

    kept = [asdict(r) for r in result["relationships"]]
    reused = [r for r in prev_rels if r.get("chunk_id") in cached_ids]
    all_rels = reused + kept

    processed = {cid: chunk_hashes.get(cid, "") for cid in cached_ids}
    processed.update(result["processed_chunks"])

    logging.info("\n" + "=" * 50)
    logging.info("RELATIONSHIP EXTRACTION COMPLETE")
    logging.info("=" * 50)
    logging.info(f"Total relationships: {len(all_rels)} ({len(reused)} reused, {len(kept)} new)")
    logging.info(f"Chunks processed: {len(processed)} | failed: {len(result['failed_chunks'])}")

    if all_rels:
        logging.info("\nBy type:")
        for t, n in Counter(r["type"] for r in all_rels).most_common():
            logging.info(f"  {n:4}  {t}")

    os.makedirs(settings.data_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "subject_id": concepts_data.get("subject_id", ""),
            "relationships": all_rels,
            "processed_chunks": processed,
            "failed_chunks": result["failed_chunks"],
        }, f, indent=2, ensure_ascii=False)

    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

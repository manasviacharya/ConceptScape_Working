import hashlib
import json
import logging
import os
from collections import Counter

from config import settings
from logging_setup import configure_logging
from relationships.common import (make_relationship_id, merge_relationships,
                                  relationship_from_dict, relationship_key,
                                  relationship_to_dict)
from relationships.cross_chunk import CrossChunkLinker, group_concepts_by_document
from relationships.extractor import RelationshipExtractor


def main():
    configure_logging()

    CHUNKS_FILE = os.path.join(settings.output_dir, "preprocessed_chunks.json")
    CONCEPTS_FILE = os.path.join(settings.data_dir, "normalized_concepts.json")
    OUTPUT_FILE = os.path.join(settings.data_dir, "relationships.json")

    for path in (CHUNKS_FILE, CONCEPTS_FILE):
        if not os.path.exists(path):
            logging.error(f"Required input not found: {path}")
            raise FileNotFoundError(path)

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)
    with open(CONCEPTS_FILE, "r", encoding="utf-8") as f:
        concepts_data = json.load(f)

    concepts = concepts_data.get("concepts", [])
    chunks = {c["chunk_id"]: c for c in chunks_data.get("chunks", [])}

    logging.info("ConceptScape Relationship Extraction starting...")
    logging.info(f"Concepts: {len(concepts)} | Chunks: {len(chunks)}")

    # Reuse previous results for chunks/documents whose inputs are unchanged, so
    # a quota-limited run resumes instead of paying for everything again.
    prev_rels, prev_chunks, prev_docs = [], {}, {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                prev = json.load(f)
            prev_rels = [relationship_from_dict(r) for r in prev.get("relationships", [])]
            prev_chunks = prev.get("processed_chunks", {})
            prev_docs = prev.get("processed_documents", {})
        except Exception:
            logging.warning("Could not read previous relationships.json — treating as full miss")

    chunk_hashes = {c["chunk_id"]: c.get("content_hash", "") for c in chunks_data.get("chunks", [])}
    cached_chunks = {cid for cid, h in prev_chunks.items() if chunk_hashes.get(cid) == h}

    # Concept ids change whenever normalization is re-run (cross-document
    # merging in particular reassigns them all). Cached relationships would then
    # point at ids that no longer exist. Re-resolve each endpoint by NAME
    # against the current concepts rather than discarding the cache and paying
    # for a full re-extraction; edges whose endpoints no longer exist are dropped.
    from relationships.common import norm as _norm
    _name_to_id = {}
    for c in concepts:
        _name_to_id[_norm(c["canonical_name"])] = c["concept_id"]
        for a in c.get("aliases", []):
            _name_to_id.setdefault(_norm(a), c["concept_id"])
    _id_to_name = {c["concept_id"]: c["canonical_name"] for c in concepts}

    if prev_rels:
        remapped, dropped = [], 0
        for r in prev_rels:
            s = _name_to_id.get(_norm(r.source_name))
            t = _name_to_id.get(_norm(r.target_name))
            if not s or not t or s == t:
                dropped += 1
                continue
            r.source_concept_id, r.target_concept_id = s, t
            r.source_name, r.target_name = _id_to_name[s], _id_to_name[t]
            r.relationship_id = make_relationship_id(s, r.type, t)
            remapped.append(r)
        if dropped:
            logging.info(f"Remapped cached relationships to current concept ids "
                         f"({len(remapped)} kept, {dropped} dropped as unresolvable/self-loop)")
        prev_rels = merge_relationships(remapped)

    # ── Stage 1: chunk-level ──────────────────────────────────────────────
    logging.info("\n--- STAGE 1: chunk-level relationships ---")
    if cached_chunks:
        logging.info(f"CACHE: {len(cached_chunks)} chunk(s) unchanged, reusing")
    stage1_input = {
        **chunks_data,
        "chunks": [c for c in chunks_data["chunks"] if c["chunk_id"] not in cached_chunks],
    }
    extractor = RelationshipExtractor()
    stage1 = extractor.process(stage1_input, concepts_data)
    reused_chunk_rels = [
        r for r in prev_rels
        if any(e.scope == "chunk" and e.chunk_id in cached_chunks for e in r.evidence)
    ]
    chunk_rels = stage1["relationships"] + reused_chunk_rels
    logging.info(f"Stage 1: {len(stage1['relationships'])} new + {len(reused_chunk_rels)} reused")

    # ── Stage 2: cross-chunk, scoped per document ─────────────────────────
    logging.info("\n--- STAGE 2: cross-chunk relationships (per document) ---")
    name_to_id, id_to_name = {}, {}
    from relationships.common import norm
    for c in concepts:
        name_to_id[norm(c["canonical_name"])] = c["concept_id"]
        for alias in c.get("aliases", []):
            name_to_id.setdefault(norm(alias), c["concept_id"])
        id_to_name[c["concept_id"]] = c["canonical_name"]

    existing_keys = {relationship_key(r.source_concept_id, r.type, r.target_concept_id) for r in chunk_rels}

    # A document's cross-chunk result stays valid while its concept set is
    # unchanged — that set is what the prompt is built from.
    def doc_signature(doc_concepts):
        return hashlib.sha256(
            "|".join(sorted(c["concept_id"] for c in doc_concepts)).encode()
        ).hexdigest()[:16]

    linker = CrossChunkLinker()
    cross_rels = []
    cross_failed = []
    processed_documents = {}
    for resource_id, doc_concepts in sorted(group_concepts_by_document(concepts).items()):
        if len(doc_concepts) < 2:
            continue
        filename = (doc_concepts[0].get("filenames") or ["?"])[0]

        sig = doc_signature(doc_concepts)
        if prev_docs.get(resource_id) == sig:
            reused = [r for r in prev_rels
                      if r.resource_id == resource_id
                      and any(e.scope == "cross_chunk" for e in r.evidence)]
            cross_rels.extend(reused)
            processed_documents[resource_id] = sig
            logging.info(f"{filename}: CACHE HIT ({len(reused)} cross-chunk edges reused)")
            continue

        already = [
            f"{r.source_name} -{r.type}-> {r.target_name}"
            for r in chunk_rels if r.resource_id == resource_id
        ]
        logging.info(f"{filename}: {len(doc_concepts)} concepts, {len(already)} existing edges")

        res = linker.link_document(
            resource_id, filename, doc_concepts, chunks, already, name_to_id, id_to_name
        )
        if res is None:
            cross_failed.append(resource_id)
            logging.error(f"CROSS-CHUNK FAILED: {filename} — re-run to retry")
            continue

        found, drops = res
        processed_documents[resource_id] = sig
        new = [r for r in found
               if relationship_key(r.source_concept_id, r.type, r.target_concept_id) not in existing_keys]
        cross_rels.extend(found)
        logging.info(
            f"  -> {len(found)} relationship(s), {len(new)} not already known "
            f"(dropped: {drops.get('unverified',0)} unverifiable, "
            f"{drops.get('unknown',0)} unknown endpoint)"
        )

    # ── Merge + dedupe ────────────────────────────────────────────────────
    all_rels = merge_relationships(chunk_rels + cross_rels)

    logging.info("\n" + "=" * 50)
    logging.info("RELATIONSHIP EXTRACTION COMPLETE")
    logging.info("=" * 50)
    logging.info(f"Stage 1 (chunk)      : {len(chunk_rels)}")
    logging.info(f"Stage 2 (cross-chunk): {len(cross_rels)}")
    logging.info(f"After dedup          : {len(all_rels)} unique relationships")
    multi = [r for r in all_rels if r.occurrence_count > 1]
    logging.info(f"Edges with >1 evidence record: {len(multi)}")
    logging.info(f"Chunks failed: {len(stage1['failed_chunks'])} | Documents failed: {len(cross_failed)}")

    if all_rels:
        logging.info("\nBy type:")
        for t, n in Counter(r.type for r in all_rels).most_common():
            logging.info(f"  {n:4}  {t}")

    connected = {r.source_concept_id for r in all_rels} | {r.target_concept_id for r in all_rels}
    logging.info(f"\nConnected concepts: {len(connected)}/{len(concepts)} "
                 f"(isolated: {len(concepts) - len(connected)})")

    os.makedirs(settings.data_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "subject_id": concepts_data.get("subject_id", ""),
            "relationships": [relationship_to_dict(r) for r in all_rels],
            "processed_chunks": {**{c: chunk_hashes.get(c, "") for c in cached_chunks}, **stage1["processed_chunks"]},
            "failed_chunks": stage1["failed_chunks"],
            "failed_documents": cross_failed,
            "processed_documents": processed_documents,
        }, f, indent=2, ensure_ascii=False)

    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

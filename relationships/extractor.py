import concurrent.futures
import json
import logging
from collections import defaultdict
from typing import Any

from config import settings
from llm_provider import LLMProvider
from relationships.common import (
    make_relationship_id,
    norm,
    verify_evidence,
    vocabulary_guidance,
)
from relationships.models import EvidenceRecord, Relationship

RELATIONSHIP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "relationships": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "source": {"type": "STRING"},
                    "target": {"type": "STRING"},
                    "type": {"type": "STRING"},
                    "evidence": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["source", "target", "type", "evidence", "confidence"],
            },
        }
    },
    "required": ["relationships"],
}


class RelationshipExtractor:
    def __init__(self):
        self.llm = LLMProvider()

    def _prompt(self, text: str, concept_names: list[str]) -> str:
        vocab = vocabulary_guidance(settings.relationship_types)
        listed = "\n".join(f"- {n}" for n in concept_names)
        return f"""
Identify relationships BETWEEN THE LISTED CONCEPTS, based only on the text below.

CONCEPTS (use these names exactly; do NOT introduce any others):
{listed}

ALLOWED RELATIONSHIP TYPES (use exactly one of these; the meaning of each
type in this schema is given — follow it, not the everyday sense of the word):
{vocab}

RULES — all are mandatory:
- Both "source" and "target" MUST be copied exactly from the concept list above.
  Never invent a concept that is not listed.
- Every relationship MUST be supported by a VERBATIM span copied from the text
  into "evidence", character-for-character. Never paraphrase there.
- Do NOT create a relationship merely because two concepts appear on the same
  slide or page. Co-occurrence is NOT evidence. The text must actually state or
  clearly imply the relationship.
- If no span supports a relationship, DO NOT emit it. Returning an empty list is
  correct and expected when the text states no relationships.
- Direction matters: "A requires B" means A depends on B, not the reverse.
- Use "related_to" only when a real relationship is evidenced but its specific
  type is unclear.
- Set "confidence" between 0.0 and 1.0.
- Prefer FEWER, well-evidenced relationships over many speculative ones.

Text:
{text}
"""

    def extract_from_chunk(self, text: str, concept_names: list[str]):
        """Returns (relationships, model_used), or None if every provider failed."""
        system_instruction = (
            "You are a knowledge-graph relationship extractor. Output valid JSON: "
            '{"relationships": [{"source": "string", "target": "string", '
            '"type": "one of the allowed types", '
            '"evidence": "verbatim span copied from the supplied text", '
            '"confidence": 0.0}]}'
        )
        result = self.llm.call(self._prompt(text, concept_names), system_instruction, RELATIONSHIP_SCHEMA)
        if result is None:
            return None

        raw_json, model_used = result
        try:
            return json.loads(raw_json).get("relationships", []), model_used
        except Exception as e:
            logging.error(f"Failed to parse relationship JSON: {e}")
            return None

    def _extract_concurrently(self, work: list[tuple]) -> dict[str, Any]:
        """
        One relationship call per chunk, issued concurrently where allowed.

        Returns chunk_id -> (relationships, model_used), or None for a chunk
        whose call failed — the same "do not cache, retry later" contract
        extract_from_chunk uses.
        """
        results: dict[str, Any] = {}
        if not work:
            return results

        workers = max(1, min(settings.relationships_max_workers, len(work)))
        logging.info(f"Extracting relationships for {len(work)} chunk(s) using {workers} worker(s)")

        if workers == 1:
            for chunk_id, chunk, names in work:
                results[chunk_id] = self.extract_from_chunk(chunk["text"], names)
            return results

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.extract_from_chunk, chunk["text"], names): chunk_id
                for chunk_id, chunk, names in work
            }
            for future in concurrent.futures.as_completed(futures):
                chunk_id = futures[future]
                try:
                    results[chunk_id] = future.result()
                except Exception:
                    logging.exception(f"Relationship extraction raised for chunk {chunk_id}")
                    results[chunk_id] = None
        return results

    def process(self, chunks_data: dict, concepts_data: dict) -> dict[str, Any]:
        chunks = {c["chunk_id"]: c for c in chunks_data.get("chunks", [])}
        canonical = concepts_data.get("concepts", [])

        # Which canonical concepts appear in which chunk, and the name -> id map
        # used to reject any endpoint the concept stage did not actually find.
        by_chunk: dict[str, list[dict]] = defaultdict(list)
        for c in canonical:
            for cid in c.get("chunk_ids", []):
                by_chunk[cid].append(c)

        name_to_id: dict[str, str] = {}
        for c in canonical:
            name_to_id[norm(c["canonical_name"])] = c["concept_id"]
            for alias in c.get("aliases", []):
                name_to_id.setdefault(norm(alias), c["concept_id"])

        id_to_name = {c["concept_id"]: c["canonical_name"] for c in canonical}

        relationships: list[Relationship] = []
        processed_chunks: dict[str, str] = {}
        failed_chunks: list[str] = []
        seen = set()
        total_returned = 0
        dropped_unverified = 0
        dropped_unknown = 0
        dropped_selfloop = 0
        dropped_badtype = 0

        # Same reasoning as the concept stage: independent, network-bound calls,
        # issued concurrently and consumed below in sorted chunk order so the
        # output is identical to a serial run.
        work = [
            (chunk_id, chunks[chunk_id], [c["canonical_name"] for c in concepts_here])
            for chunk_id, concepts_here in sorted(by_chunk.items())
            if chunk_id in chunks and len(concepts_here) >= 2  # an edge needs two endpoints
        ]
        llm_results = self._extract_concurrently(work)

        for chunk_id, chunk, names in work:
            logging.info(f"Extracting relationships: {chunk_id} ({len(names)} concepts)")

            result = llm_results.get(chunk_id)
            if result is None:
                failed_chunks.append(chunk_id)
                logging.error(f"RELATIONSHIP EXTRACTION FAILED: {chunk_id} — not cached, re-run to retry")
                continue

            rels, model_used = result
            total_returned += len(rels)
            processed_chunks[chunk_id] = chunk.get("content_hash", "")

            for r in rels:
                rtype = (r.get("type") or "").strip().lower()
                if rtype not in settings.relationship_types:
                    dropped_badtype += 1
                    continue

                src_id = name_to_id.get(norm(r.get("source", "")))
                tgt_id = name_to_id.get(norm(r.get("target", "")))
                if not src_id or not tgt_id:
                    dropped_unknown += 1
                    logging.warning(
                        f"DROPPED (endpoint is not a known concept): "
                        f"{r.get('source')!r} -> {r.get('target')!r}"
                    )
                    continue
                if src_id == tgt_id:
                    dropped_selfloop += 1
                    continue

                verified = verify_evidence(
                    r.get("evidence", ""),
                    [("text", chunk["text"]), ("raw_page_text", chunk.get("raw_page_text", ""))],
                )
                if settings.require_evidence and verified is None:
                    dropped_unverified += 1
                    logging.warning(
                        f"DROPPED (evidence not in source): {r.get('source')} "
                        f"-{rtype}-> {r.get('target')} | {str(r.get('evidence'))[:70]!r}"
                    )
                    continue

                key = (src_id, rtype, tgt_id, chunk_id)
                if key in seen:
                    continue
                seen.add(key)

                conf = r.get("confidence")
                conf = float(conf) if isinstance(conf, (int, float)) else 0.0

                relationships.append(Relationship(
                    relationship_id=make_relationship_id(src_id, rtype, tgt_id),
                    source_concept_id=src_id,
                    source_name=id_to_name.get(src_id, ""),
                    target_concept_id=tgt_id,
                    target_name=id_to_name.get(tgt_id, ""),
                    type=rtype,
                    resource_id=chunk.get("resource_id", ""),
                    evidence=[EvidenceRecord(
                        text=r.get("evidence", ""),
                        verified_against=verified or "",
                        chunk_id=chunk_id,
                        filename=chunk.get("filename", ""),
                        location_number=chunk.get("location_number", 0),
                        location_type=chunk.get("location_type", ""),
                        confidence=conf,
                        model_used=model_used,
                        scope="chunk",
                    )],
                ))

        if total_returned:
            logging.info(
                f"Relationships: {len(relationships)} kept of {total_returned} returned "
                f"({dropped_unverified} unverifiable, {dropped_unknown} unknown endpoint, "
                f"{dropped_selfloop} self-loop, {dropped_badtype} bad type)"
            )
        if failed_chunks:
            logging.warning(f"{len(failed_chunks)} chunk(s) failed — not cached, re-run to retry")

        return {
            "relationships": relationships,
            "processed_chunks": processed_chunks,
            "failed_chunks": failed_chunks,
        }

import json
import logging
import os
import re
import unicodedata
import uuid
from typing import List, Dict, Any, Optional, Tuple

from config import settings
from llm_provider import LLMProvider


CONCEPT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "concepts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "concept_name": {"type": "STRING"},
                    "definition": {"type": "STRING"},
                    "evidence": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "relationships": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "target": {"type": "STRING"},
                                "type": {"type": "STRING"},
                            },
                            "required": ["target", "type"],
                        },
                    },
                },
                "required": [
                    "concept_name", "definition", "evidence", "confidence",
                    "keywords", "relationships",
                ],
            },
        }
    },
    "required": ["concepts"],
}


def _load_previous_extraction_cache() -> Tuple[dict, dict]:
    """Returns (processed_chunks, concepts_by_chunk) from previous output."""
    cache_path = os.path.join(settings.data_dir, "extracted_concepts.json")
    if not os.path.exists(cache_path):
        return {}, {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        processed = data.get("processed_chunks", {})
        concepts_by_chunk: Dict[str, list] = {}
        for concept in data.get("concepts", []):
            src = concept.get("source_reference", {})
            chunk_id = src.get("chunk_id")
            if chunk_id:
                concepts_by_chunk.setdefault(chunk_id, []).append(concept)
        return processed, concepts_by_chunk
    except Exception:
        logging.warning("Could not load previous extracted_concepts.json for caching — treating as full cache miss")
        return {}, {}


def _norm_for_match(s: str) -> str:
    """
    Normalise text for evidence membership checks.

    Exact substring matching fails on differences that are not real
    mismatches — the model re-wraps lines, changes case, or collapses the
    spacing it was given. NFKC + whitespace collapse + casefold removes
    exactly those, while still requiring the words themselves to be present.
    """
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def _verify_evidence(evidence: str, chunk_text: str, raw_page_text: str) -> Optional[str]:
    """
    Returns "text" / "raw_page_text" if the span occurs in that source, else None.

    Asking the LLM for evidence is not enough — it will invent quotes. This is
    the check that makes grounding real rather than another hallucinated field.
    """
    if not evidence or not evidence.strip():
        return None
    ev = _norm_for_match(evidence)
    if len(ev) < 10:  # too short to be meaningful evidence
        return None
    if ev in _norm_for_match(chunk_text):
        return "text"
    if raw_page_text and ev in _norm_for_match(raw_page_text):
        return "raw_page_text"
    return None


class ConceptExtractor:
    def __init__(self):
        self.llm = LLMProvider()

    def extract_from_chunk(self, text: str) -> Optional[Tuple[List[Dict[str, Any]], str]]:
        """
        Returns (concepts, model_used), or None if every provider failed.

        None and [] mean different things and must not be conflated: [] is a
        successful call that found no concepts (cacheable), None is a failed
        call (must NOT be cached, so a later run retries it). Rate limits
        surface as None, which is what makes a partial run resumable.
        """
        # The ungrounded prompt is the ablation baseline: what a conventional
        # "extract the concepts" instruction produces with no evidence
        # requirement. Keeping it here rather than in the harness means the
        # comparison differs only in the instruction, not in parsing, schema
        # or provider — so any measured difference is attributable to grounding.
        if settings.extraction_grounded_prompt:
            prompt = f"""
Extract meaningful educational concepts from the text below.

RULES — follow all of them:
- Every concept MUST be supported by a VERBATIM span copied from the text.
  Copy it character-for-character into the "evidence" field. Never summarise
  or paraphrase in that field.
- If you cannot copy an exact supporting span, DO NOT emit the concept.
- Do NOT extract: equations or formulas as concepts, slide or section
  titles, agenda/outline items, generic single words that the text does not
  actually define (e.g. "Error", "Sample", "Data"), or author/course
  metadata.
- Extract concepts a student could genuinely learn and be tested on.
- The definition must come from the text, NOT from your own knowledge. If
  the text only names a concept without explaining it, either omit it or
  state the definition exactly as the text does.
- Prefer FEWER, well-grounded concepts over many weak ones.
- Set "confidence" between 0.0 and 1.0: how sure you are this is a real,
  well-supported educational concept given only this text.

Text:
{text}
"""
        else:
            prompt = f"""
Extract the educational concepts from the text below.

For each concept give its name, a definition, and relevant keywords.
Also provide an "evidence" field with text related to the concept, and a
"confidence" between 0.0 and 1.0.

Text:
{text}
"""
        system_instruction = (
            "You are an AI educational extraction engine. "
            "You must output valid JSON matching this schema: "
            "{\"concepts\": [{\"concept_name\": \"string\", \"definition\": \"string\", "
            "\"evidence\": \"verbatim span copied from the supplied text\", "
            "\"confidence\": 0.0, "
            "\"keywords\": [\"string\"], \"relationships\": [{\"target\": \"string\", "
            "\"type\": \"requires|related_to|part_of\"}]}]}"
        )

        result = self.llm.call(prompt, system_instruction, CONCEPT_SCHEMA)
        if result is None:
            return None

        result_json, model_used = result
        try:
            result_data = json.loads(result_json)
            return result_data.get("concepts", []), model_used
        except (TypeError, json.JSONDecodeError) as e:
            logging.error(f"Failed to parse concept JSON output: {e}")
            return None

    def process_chunks(self, preprocessed_data: dict) -> Dict[str, Any]:
        """Consumes flat TextChunk list from preprocessed_chunks.json."""
        all_concepts = []
        processed_chunks: Dict[str, str] = {}
        failed_chunks: List[str] = []
        skipped_chunks: List[Dict[str, Any]] = []
        subject_id = preprocessed_data.get("subject_id")
        explicit_skips = set(settings.extraction_skip_chunks)
        seen_chunk_ids = set()

        prev_processed, prev_concepts = _load_previous_extraction_cache()

        skipped_short = 0
        dropped_unverified = 0
        dropped_concepts: List[Dict[str, Any]] = []
        dropped_low_conf = 0
        total_returned = 0

        for chunk in preprocessed_data.get("chunks", []):
            text = chunk.get("text", "").strip()
            if not text:
                continue

            chunk_id = chunk.get("chunk_id", "")
            if chunk_id:
                seen_chunk_ids.add(chunk_id)

            if chunk_id in explicit_skips:
                skipped_chunks.append({
                    "chunk_id": chunk_id,
                    "resource_id": chunk.get("resource_id", ""),
                    "filename": chunk.get("filename", ""),
                    "source_type": chunk.get("source_type", ""),
                    "location_type": chunk.get("location_type", ""),
                    "location_number": chunk.get("location_number", 0),
                    "content_hash": chunk.get("content_hash", ""),
                    "reason": "explicitly skipped after provider failure",
                })
                logging.warning(
                    f"SKIP (explicit provider-failure decision): chunk {chunk_id}"
                )
                continue

            # Chunks this short are slide titles and section headers
            # ("Introduction", "THANK YOU"). They carry no extractable concept,
            # so calling the LLM on them only wastes quota and pollutes the
            # graph with junk nodes. Recorded as processed so they stay cached.
            if len(text) < settings.extraction_min_chunk_chars:
                logging.info(f"SKIP (too short, {len(text)} chars): chunk {chunk_id}")
                skipped_short += 1
                if chunk_id:
                    processed_chunks[chunk_id] = chunk.get("content_hash", "")
                continue

            content_hash = chunk.get("content_hash", "")
            resource_id = chunk.get("resource_id", "")
            source_type = chunk.get("source_type", "")
            filename = chunk.get("filename", "")
            location_type = chunk.get("location_type", "")
            location_number = chunk.get("location_number", 0)

            if chunk_id and content_hash and prev_processed.get(chunk_id) == content_hash:
                logging.info(f"CACHE HIT (unchanged): chunk {chunk_id}")
                processed_chunks[chunk_id] = content_hash
                all_concepts.extend(prev_concepts.get(chunk_id, []))
                continue

            logging.info(f"CACHE MISS (extracting): chunk {chunk_id}")
            logging.info(f"Processing {source_type.upper()} {location_type} {location_number} ({filename})")

            result = self.extract_from_chunk(text)
            if result is None:
                failed_chunks.append(chunk_id)
                logging.error(f"EXTRACTION FAILED: chunk {chunk_id} — not cached, re-run to retry")
                continue

            concepts, model_used = result
            total_returned += len(concepts)
            raw_page_text = chunk.get("raw_page_text", "")

            kept = []
            for concept in concepts:
                evidence = concept.get("evidence", "") or ""
                verified = _verify_evidence(evidence, text, raw_page_text)

                if settings.require_evidence and verified is None:
                    dropped_unverified += 1
                    # Recorded, not discarded: this is exactly the set the
                    # verification step removes, so keeping it lets the ablation
                    # measure the verifier's effect without a second LLM run.
                    dropped_concepts.append({
                        "concept_name": concept.get("concept_name", ""),
                        "definition": concept.get("definition", ""),
                        "evidence": evidence,
                        "confidence": concept.get("confidence"),
                        "chunk_id": chunk_id,
                        "filename": filename,
                        "reason": "evidence_not_in_source",
                    })
                    logging.warning(
                        f"DROPPED (evidence not found in source): "
                        f"{concept.get('concept_name','?')!r} — evidence={evidence[:90]!r}"
                    )
                    continue

                conf = concept.get("confidence")
                conf = float(conf) if isinstance(conf, (int, float)) else 0.0
                if conf < settings.min_concept_confidence:
                    dropped_low_conf += 1
                    logging.info(
                        f"DROPPED (confidence {conf} < {settings.min_concept_confidence}): "
                        f"{concept.get('concept_name','?')!r}"
                    )
                    continue

                concept["_evidence_verified_against"] = verified or ""
                concept["_confidence"] = conf
                kept.append(concept)

            logging.info(
                f"Extracted {len(kept)} concept mention(s) "
                f"({len(concepts) - len(kept)} dropped) via {model_used}"
            )

            processed_chunks[chunk_id] = content_hash

            for concept in kept:
                concept_mention = {
                    "concept_id": f"mention_{uuid.uuid4().hex[:8]}",
                    "concept_name": concept.get("concept_name", ""),
                    "definition": concept.get("definition", ""),
                    "evidence": concept.get("evidence", ""),
                    "evidence_verified_against": concept.get("_evidence_verified_against", ""),
                    "confidence": concept.get("_confidence", 0.0),
                    "model_used": model_used,
                    "keywords": concept.get("keywords", []),
                    "relationships": [
                        {"target": r.get("target"), "type": r.get("type")}
                        for r in concept.get("relationships", [])
                    ],
                    "source_reference": {
                        "resource_id": resource_id,
                        "resource_type": source_type,
                        "filename": filename,
                        "chunk_id": chunk_id,
                        "content_hash": content_hash,
                    },
                    "workspace_id": subject_id
                }

                # location_number is always recorded; the typed alias below is
                # what the UI reads to label a citation. Without the generic
                # field, any source whose unit is not a page or slide — a video
                # timestamp, say — loses its position entirely.
                concept_mention["source_reference"]["location_type"] = location_type
                concept_mention["source_reference"]["location_number"] = location_number

                if location_type == "page":
                    concept_mention["source_reference"]["page_number"] = location_number
                elif location_type == "slide":
                    concept_mention["source_reference"]["slide_number"] = location_number
                elif location_type == "timestamp":
                    concept_mention["source_reference"]["timestamp_seconds"] = location_number

                all_concepts.append(concept_mention)

        if total_returned:
            pct = 100.0 * dropped_unverified / total_returned
            logging.info(
                f"Evidence verification: {dropped_unverified}/{total_returned} "
                f"({pct:.1f}%) dropped as unverifiable; {dropped_low_conf} dropped on confidence"
            )

        if skipped_short:
            logging.info(f"Skipped {skipped_short} chunk(s) shorter than {settings.extraction_min_chunk_chars} chars")

        if failed_chunks:
            logging.warning(
                f"{len(failed_chunks)} chunk(s) failed extraction and were NOT cached. "
                f"Re-run to retry only these."
            )

        unknown_skips = explicit_skips - seen_chunk_ids
        if unknown_skips:
            raise ValueError(
                "Configured extraction skips do not exist in the chunk manifest: "
                + ", ".join(sorted(unknown_skips))
            )

        return {
            "subject_id": subject_id,
            "processed_chunks": processed_chunks,
            "concepts": all_concepts,
            "failed_chunks": failed_chunks,
            "skipped_chunks": skipped_chunks,
            "dropped_concepts": dropped_concepts,
        }

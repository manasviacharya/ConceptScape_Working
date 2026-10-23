import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from llm_provider import LLMProvider
from relationships.common import make_relationship_id, norm, verify_evidence
from relationships.models import EvidenceRecord, Relationship

CROSS_CHUNK_SCHEMA = {
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


class CrossChunkLinker:
    """
    Second relationship pass, scoped to one document.

    Chunk-level extraction can only connect concepts that happen to share a
    chunk. A concept defined on slide 3 and used on slide 7 therefore stays
    isolated even when the document plainly relates them. This stage widens the
    window to the document while keeping the evidence rule intact: a span must
    still be found verbatim in one of that document's chunks.

    The whole document is NOT dumped into the prompt. Context is assembled from
    each concept's own verified evidence and definition, so the model sees real
    source text and nothing else.
    """

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.llm = llm or LLMProvider()

    def _build_context(self, concepts: List[dict], chunks: Dict[str, dict]) -> str:
        blocks = []
        for c in concepts:
            passages = []
            for ev in (c.get("evidence") or [])[:3]:
                passages.append(f'    "{ev}"')
            # Fall back to the concept's source chunks when it carries no
            # evidence spans, so it can still participate rather than being
            # silently excluded from linking.
            if not passages:
                for cid in (c.get("chunk_ids") or [])[:1]:
                    ch = chunks.get(cid)
                    if ch:
                        passages.append(f'    "{ch["text"][:300]}"')
            block = f'- {c["canonical_name"]}\n  definition: {c.get("definition","")}\n  source passages:\n'
            block += "\n".join(passages) if passages else "    (none)"
            blocks.append(block)
        return "\n".join(blocks)

    def _prompt(self, filename: str, context: str, existing: List[str]) -> str:
        vocab = ", ".join(settings.relationship_types)
        already = "\n".join(f"- {e}" for e in existing) if existing else "(none yet)"
        return f"""
Below are concepts extracted from a single document ("{filename}"), each with
its definition and VERBATIM passages from that document.

Identify relationships between these concepts that the SOURCE PASSAGES support,
including relationships expressed across different passages.

CONCEPTS AND THEIR SOURCE PASSAGES:
{context}

RELATIONSHIPS ALREADY FOUND (do not repeat these):
{already}

ALLOWED RELATIONSHIP TYPES:
{vocab}

RULES — all mandatory:
- "source" and "target" MUST be copied exactly from the concept names above.
  Never introduce a concept that is not listed.
- "evidence" MUST be a VERBATIM span copied from the source passages shown
  above, character-for-character. It will be checked against the document and
  discarded if it does not appear there.
- Create a relationship ONLY when the passages state or clearly imply it.
  Do NOT create one because two concepts appear in the same document, sit on
  nearby pages, co-occur frequently, or are related in general domain
  knowledge you happen to have. Your own knowledge is NOT evidence.
- If the passages do not support a relationship, omit it. Returning an empty
  list is a correct and expected answer.
- Direction matters: "A requires B" means A depends on B, not the reverse.
- Use "related_to" only when a real relationship is evidenced but its specific
  type is unclear.
- Prefer FEWER, well-evidenced relationships over many speculative ones.
"""

    def link_document(
        self,
        resource_id: str,
        filename: str,
        concepts: List[dict],
        chunks: Dict[str, dict],
        existing_pairs: List[str],
        name_to_id: Dict[str, str],
        id_to_name: Dict[str, str],
    ) -> Optional[Tuple[List[Relationship], Dict[str, int]]]:
        """Returns (relationships, drop_counts), or None if every provider failed."""
        if len(concepts) < 2:
            return [], {}

        # A document with many concepts produces a prompt and response large
        # enough that Groq's JSON-mode validator rejects the generation
        # outright. Split into batches, repeating the most frequent concepts in
        # every batch as anchors so hub relationships still surface across the
        # split rather than being lost at batch boundaries.
        limit = settings.cross_chunk_max_concepts
        if len(concepts) > limit:
            ranked = sorted(concepts, key=lambda c: -c.get("occurrence_count", 0))
            anchors = ranked[: settings.cross_chunk_anchor_concepts]
            anchor_ids = {c["concept_id"] for c in anchors}
            rest = [c for c in concepts if c["concept_id"] not in anchor_ids]

            step = max(1, limit - len(anchors))
            batches = [anchors + rest[i:i + step] for i in range(0, len(rest), step)]
            logging.info(
                f"  {filename}: {len(concepts)} concepts — splitting into "
                f"{len(batches)} batches of <={limit} (with {len(anchors)} anchors)"
            )

            all_rels, all_drops, any_ok = [], {}, False
            for i, batch in enumerate(batches, 1):
                res = self.link_document(
                    resource_id, filename, batch, chunks, existing_pairs, name_to_id, id_to_name
                )
                if res is None:
                    logging.warning(f"  batch {i}/{len(batches)} failed")
                    continue
                any_ok = True
                rels, drops = res
                all_rels.extend(rels)
                for k, v in drops.items():
                    all_drops[k] = all_drops.get(k, 0) + v
            return (all_rels, all_drops) if any_ok else None

        system_instruction = (
            "You are a knowledge-graph relationship extractor. Output valid JSON: "
            '{"relationships": [{"source": "string", "target": "string", '
            '"type": "one of the allowed types", '
            '"evidence": "verbatim span copied from the supplied passages", '
            '"confidence": 0.0}]}'
        )
        prompt = self._prompt(filename, self._build_context(concepts, chunks), existing_pairs)

        result = self.llm.call(prompt, system_instruction, CROSS_CHUNK_SCHEMA)
        if result is None:
            return None

        raw_json, model_used = result
        try:
            rels = json.loads(raw_json).get("relationships", [])
        except Exception as e:
            logging.error(f"Failed to parse cross-chunk JSON for {filename}: {e}")
            return None

        # Evidence may come from ANY chunk of this document — that is the whole
        # point of the cross-chunk pass — so every chunk is a candidate source.
        doc_chunk_ids = {cid for c in concepts for cid in (c.get("chunk_ids") or [])}
        sources = []
        for cid in sorted(doc_chunk_ids):
            ch = chunks.get(cid)
            if ch:
                sources.append((cid, ch["text"]))
                if ch.get("raw_page_text"):
                    sources.append((cid, ch["raw_page_text"]))

        chunk_meta = {cid: chunks[cid] for cid in doc_chunk_ids if cid in chunks}
        drops = {"unverified": 0, "unknown": 0, "selfloop": 0, "badtype": 0}
        out: List[Relationship] = []

        for r in rels:
            rtype = (r.get("type") or "").strip().lower()
            if rtype not in settings.relationship_types:
                drops["badtype"] += 1
                continue

            src_id = name_to_id.get(norm(r.get("source", "")))
            tgt_id = name_to_id.get(norm(r.get("target", "")))
            if not src_id or not tgt_id:
                drops["unknown"] += 1
                continue
            if src_id == tgt_id:
                drops["selfloop"] += 1
                continue

            verified_in = verify_evidence(r.get("evidence", ""), sources)
            if settings.require_evidence and verified_in is None:
                drops["unverified"] += 1
                logging.warning(
                    f"DROPPED cross-chunk (evidence not in document): "
                    f"{r.get('source')} -{rtype}-> {r.get('target')} | "
                    f"{str(r.get('evidence'))[:70]!r}"
                )
                continue

            meta = chunk_meta.get(verified_in, {})
            conf = r.get("confidence")
            conf = float(conf) if isinstance(conf, (int, float)) else 0.0

            out.append(Relationship(
                relationship_id=make_relationship_id(src_id, rtype, tgt_id),
                source_concept_id=src_id,
                source_name=id_to_name.get(src_id, ""),
                target_concept_id=tgt_id,
                target_name=id_to_name.get(tgt_id, ""),
                type=rtype,
                resource_id=resource_id,
                evidence=[EvidenceRecord(
                    text=r.get("evidence", ""),
                    verified_against=verified_in or "",
                    chunk_id=verified_in or "",
                    filename=meta.get("filename", filename),
                    location_number=meta.get("location_number", 0),
                    confidence=conf,
                    model_used=model_used,
                    scope="cross_chunk",
                )],
            ))

        return out, drops


def group_concepts_by_document(concepts: List[dict]) -> Dict[str, List[dict]]:
    """
    Index concepts by document.

    After cross-document merging a concept belongs to several documents, so it
    appears under each — the cross-chunk pass reasons about one document at a
    time and needs every concept present in that document.
    """
    by_doc: Dict[str, List[dict]] = defaultdict(list)
    for c in concepts:
        for rid in (c.get("resource_ids") or []):
            by_doc[rid].append(c)
    return by_doc

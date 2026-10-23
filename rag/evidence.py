from typing import Dict, List

from config import settings
from rag.models import Citation


def assemble(
    results,
    concepts_by_id: Dict[str, dict],
    relationships: List[dict],
    max_items: int = None,
) -> List[Citation]:
    """
    Turn retrieval hits into numbered, source-attributed evidence.

    Three kinds are gathered, in priority order:

      concept      — the concept's definition and its verified evidence spans
      relationship — the evidence span that justified an edge between two
                     retrieved concepts; this is what lets the model answer
                     "what does X require" from the graph rather than guessing
      chunk        — raw source text, for open questions whose answer was never
                     captured as a concept

    Only edges whose BOTH endpoints were retrieved are included. An edge to an
    unretrieved concept would put a claim in front of the model without the
    context needed to use it correctly.
    """
    max_items = max_items or settings.rag_max_citations
    citations: List[Citation] = []
    seen_texts = set()
    retrieved_ids = {r.id for r in results if r.kind == "concept"}

    def add(kind, text, **kw):
        key = (kind, text.strip()[:160])
        if not text.strip() or key in seen_texts:
            return
        seen_texts.add(key)
        citations.append(Citation(index=len(citations) + 1, kind=kind, text=text.strip(), **kw))

    # ── 1. one definition per retrieved concept ───────────────────────────
    # Definitions come first so every retrieved concept is represented before
    # any single concept gets a second slot.
    for r in results:
        if r.kind != "concept" or len(citations) >= max_items:
            continue
        concept = concepts_by_id.get(r.id, {})
        definition = concept.get("definition") or r.text
        if definition:
            add("concept", definition,
                concept_name=r.name,
                filename=(r.filenames or [""])[0],
                page_number=(r.page_numbers or [0])[0],
                chunk_id=(r.chunk_ids or [""])[0])

    # ── 2. relationships between retrieved concepts ───────────────────────
    # Deliberately ahead of extra per-concept evidence spans. Definitions alone
    # cannot answer "what does X require" — the edge evidence is what carries
    # the connection, and if it queues behind spans it never reaches the
    # generator at all.
    for rel in relationships:
        if len(citations) >= max_items:
            break
        if rel["source_concept_id"] not in retrieved_ids or rel["target_concept_id"] not in retrieved_ids:
            continue
        label = f"{rel['source_name']} -{rel['type']}-> {rel['target_name']}"
        for ev in (rel.get("evidence") or [])[:1]:
            add("relationship", ev.get("text", ""),
                relationship=label,
                filename=ev.get("filename", ""),
                page_number=ev.get("location_number", 0),
                chunk_id=ev.get("chunk_id", ""))

    # ── 3. remaining per-concept evidence spans ───────────────────────────
    for r in results:
        if r.kind != "concept" or len(citations) >= max_items:
            continue
        concept = concepts_by_id.get(r.id, {})
        for span in (concept.get("evidence") or [])[:settings.rag_evidence_per_concept]:
            if len(citations) >= max_items:
                break
            add("concept", span,
                concept_name=r.name,
                filename=(r.filenames or [""])[0],
                page_number=(r.page_numbers or [0])[0],
                chunk_id=(r.chunk_ids or [""])[0])

    # ── chunks ────────────────────────────────────────────────────────────
    for r in results:
        if r.kind != "chunk" or len(citations) >= max_items:
            continue
        add("chunk", r.text[:settings.rag_chunk_char_limit],
            filename=(r.filenames or [""])[0],
            page_number=(r.page_numbers or [0])[0],
            chunk_id=r.id)

    return citations


def format_for_prompt(citations: List[Citation]) -> str:
    lines = []
    for c in citations:
        if c.kind == "relationship":
            head = f"[{c.index}] (relationship: {c.relationship}) — {c.label()}"
        elif c.concept_name:
            head = f"[{c.index}] (concept: {c.concept_name}) — {c.label()}"
        else:
            head = f"[{c.index}] (source text) — {c.label()}"
        lines.append(f"{head}\n    {c.text}")
    return "\n".join(lines)


from config import settings
from rag.models import Citation


def assemble(
    results,
    concepts_by_id: dict[str, dict],
    relationships: list[dict],
    max_items: int = None,
) -> list[Citation]:
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
    citations: list[Citation] = []
    seen_texts = set()
    retrieved_ids = {r.id for r in results if r.kind == "concept"}

    def add(kind, text, **kw):
        key = (kind, text.strip()[:160])
        if not text.strip() or key in seen_texts:
            return
        seen_texts.add(key)
        citations.append(Citation(index=len(citations) + 1, kind=kind, text=text.strip(), **kw))

    def provenance(record: dict, fallback) -> dict:
        """
        Citation fields for one span, taken from the span's own record.

        A fused concept unions filenames and page_numbers over every merged
        mention, so indexing those lists attributes a span to whichever source
        sorted first rather than the one it was read from. The per-span record
        is the only thing that knows. The fallback is used for pre-migration
        artifacts that predate these records, where the first source is still
        the best available guess.
        """
        if record:
            return {
                "filename": record.get("filename", ""),
                "page_number": record.get("location_number", 0) or 0,
                "location_type": record.get("location_type", ""),
                "chunk_id": record.get("chunk_id", ""),
            }
        return {
            "filename": (fallback.filenames or [""])[0],
            "page_number": (fallback.page_numbers or [0])[0],
            "location_type": _location_type_for(fallback),
            "chunk_id": (fallback.chunk_ids or [""])[0],
        }

    def _location_type_for(result) -> str:
        """
        Position type for a result that has no per-span record.

        Chunks carry theirs directly. A concept spanning several sources may
        mix pages and slides, so a type is only claimed when every location
        agrees — otherwise the position is rendered bare rather than labelled
        wrongly.
        """
        extra = result.extra or {}
        if extra.get("location_type"):
            return extra["location_type"]
        types = {loc.get("type") for loc in extra.get("locations", []) if loc.get("type")}
        return types.pop() if len(types) == 1 else ""

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
                **provenance(concept.get("definition_source") or {}, r))

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
                page_number=ev.get("location_number", 0) or 0,
                location_type=ev.get("location_type", ""),
                chunk_id=ev.get("chunk_id", ""))

    # ── 3. remaining per-concept evidence spans ───────────────────────────
    for r in results:
        if r.kind != "concept" or len(citations) >= max_items:
            continue
        concept = concepts_by_id.get(r.id, {})
        # Prefer the records, which pair each span with the source it was read
        # from. Bare strings are the pre-migration shape and keep the old
        # first-source behaviour rather than failing.
        records = concept.get("evidence_records") or [
            {"text": span} for span in (concept.get("evidence") or [])
        ]
        for record in records[:settings.rag_evidence_per_concept]:
            if len(citations) >= max_items:
                break
            add("concept", record.get("text", ""),
                concept_name=r.name,
                **provenance(record if record.get("filename") else {}, r))

    # ── chunks ────────────────────────────────────────────────────────────
    for r in results:
        if r.kind != "chunk" or len(citations) >= max_items:
            continue
        add("chunk", r.text[:settings.rag_chunk_char_limit],
            filename=(r.filenames or [""])[0],
            page_number=(r.page_numbers or [0])[0],
            location_type=_location_type_for(r),
            chunk_id=r.id)

    return citations


def format_for_prompt(citations: list[Citation]) -> str:
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

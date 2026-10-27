from dataclasses import dataclass, field


@dataclass
class CanonicalConcept:
    """
    One concept merged from every mention of it across the whole corpus.

    A concept spanning several documents carries all of them in resource_ids —
    "Stochastic Gradient Descent" taught in four decks is ONE node citing four
    sources, not four disconnected nodes. Every provenance field is a UNION
    over the merged mentions and is never truncated: citations in later phases
    trace back through these lists.
    """
    concept_id: str
    canonical_name: str
    resource_ids: list[str]
    definition: str
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    mention_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    filenames: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    # Typed positions: [{"type": "page"|"slide"|"timestamp", "number", "filename"}]
    # page_numbers alone cannot say whether 57 means page 57 or 57 seconds.
    locations: list[dict] = field(default_factory=list)
    # Verified spans as bare text, kept for readers that only want the quotes.
    evidence: list[str] = field(default_factory=list)
    # The same spans, each carrying the provenance of the mention it came from:
    # [{"text", "filename", "location_type", "location_number", "chunk_id",
    #   "resource_id"}]
    #
    # A fused concept unions filenames and page_numbers across every merged
    # mention, so position i of `evidence` has no relationship to position i of
    # `filenames`. Citing a span therefore cannot be done from those lists
    # without guessing — and guessing meant every span of a multi-source
    # concept was attributed to whichever file happened to sort first. Keeping
    # the span and its origin in one record is what makes a citation point at
    # the document and page the quote was actually read from.
    evidence_records: list[dict] = field(default_factory=list)
    # Provenance of the single mention the definition was taken from. The
    # definition is never stitched from several mentions, so it has exactly one
    # source and should be cited against that one rather than the group's first
    # filename.
    definition_source: dict = field(default_factory=dict)
    occurrence_count: int = 0
    mean_confidence: float = 0.0
    models_used: list[str] = field(default_factory=list)

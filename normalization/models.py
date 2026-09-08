from dataclasses import dataclass, field
from typing import List


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
    resource_ids: List[str]
    definition: str
    aliases: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    mention_ids: List[str] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    # Typed positions: [{"type": "page"|"slide"|"timestamp", "number", "filename"}]
    # page_numbers alone cannot say whether 57 means page 57 or 57 seconds.
    locations: List[dict] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    occurrence_count: int = 0
    mean_confidence: float = 0.0
    models_used: List[str] = field(default_factory=list)

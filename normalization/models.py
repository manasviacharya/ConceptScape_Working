from dataclasses import dataclass, field
from typing import List


@dataclass
class CanonicalConcept:
    """
    One concept within a single document, merged from all its mentions.

    Cross-document merging is a later phase — a CanonicalConcept therefore
    belongs to exactly one resource_id. Every provenance field is a UNION over
    the merged mentions and is never truncated on merge: citations in later
    phases trace back through these lists.
    """
    concept_id: str
    canonical_name: str
    resource_id: str
    definition: str
    aliases: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    mention_ids: List[str] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    occurrence_count: int = 0
    mean_confidence: float = 0.0
    models_used: List[str] = field(default_factory=list)

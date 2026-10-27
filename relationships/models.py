from dataclasses import dataclass, field


@dataclass
class EvidenceRecord:
    """
    One piece of source text supporting a relationship.

    A relationship can be stated in several places; each occurrence is kept as
    its own record so provenance is never collapsed. `scope` distinguishes an
    edge found inside a single chunk from one assembled across chunks of the
    same document.
    """
    text: str
    verified_against: str          # "text" | "raw_page_text"
    chunk_id: str
    filename: str
    location_number: int
    confidence: float
    model_used: str
    scope: str                     # "chunk" | "cross_chunk"
    # "page" | "slide" | "timestamp". location_number alone cannot say whether
    # 12 means page 12, slide 12, or 12 seconds into a recording, so a citation
    # built from it has to guess — and a guessed "p12" for a deck points the
    # reader at a page that does not exist. Defaulted so relationships written
    # before this field was added still load.
    location_type: str = ""


@dataclass
class Relationship:
    """
    One evidence-grounded edge between two canonical concepts.

    Logical identity is (source_concept_id, type, target_concept_id) — the same
    relationship found in five places is ONE edge carrying five evidence
    records, not five duplicate edges.

    Both endpoints are concept_ids that already exist; an edge may never
    introduce a concept that concept extraction did not find.
    """
    relationship_id: str
    source_concept_id: str
    source_name: str
    target_concept_id: str
    target_name: str
    type: str
    resource_id: str
    evidence: list[EvidenceRecord] = field(default_factory=list)

    @property
    def occurrence_count(self) -> int:
        return len(self.evidence)

    @property
    def mean_confidence(self) -> float:
        if not self.evidence:
            return 0.0
        return round(sum(e.confidence for e in self.evidence) / len(self.evidence), 3)

    @property
    def chunk_ids(self) -> list[str]:
        seen, out = set(), []
        for e in self.evidence:
            if e.chunk_id and e.chunk_id not in seen:
                seen.add(e.chunk_id)
                out.append(e.chunk_id)
        return out

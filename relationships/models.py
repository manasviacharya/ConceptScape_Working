from dataclasses import dataclass


@dataclass
class Relationship:
    """
    One evidence-grounded edge between two canonical concepts.

    Both endpoints are concept_ids that already exist — an edge is never
    allowed to introduce a concept that concept extraction did not find.
    `evidence` is a verbatim span from the chunk, verified to occur there;
    an edge without one is discarded rather than stored.
    """
    relationship_id: str
    source_concept_id: str
    source_name: str
    target_concept_id: str
    target_name: str
    type: str
    evidence: str
    evidence_verified_against: str
    confidence: float
    chunk_id: str
    filename: str
    location_number: int
    resource_id: str
    model_used: str

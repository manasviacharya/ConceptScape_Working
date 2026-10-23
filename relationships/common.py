import hashlib
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from relationships.models import EvidenceRecord, Relationship


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip().casefold()


def verify_evidence(evidence: str, sources: Iterable[str]) -> Optional[str]:
    """
    Return the label of the first source containing the span, else None.

    `sources` is an iterable of (label, text) pairs. Chunk-level extraction
    passes that chunk's own text; the cross-chunk stage passes every chunk in
    the document, which is what lets a relationship stated on slide 7 support
    an edge between concepts introduced on slides 3 and 7.
    """
    if not evidence or not evidence.strip():
        return None
    ev = norm(evidence)
    if len(ev) < 10:  # too short to be meaningful evidence
        return None
    for label, text in sources:
        if ev in norm(text):
            return label
    return None


def relationship_key(source_id: str, rtype: str, target_id: str) -> str:
    return f"{source_id}|{rtype}|{target_id}"


def make_relationship_id(source_id: str, rtype: str, target_id: str) -> str:
    digest = hashlib.sha256(relationship_key(source_id, rtype, target_id).encode()).hexdigest()[:12]
    return f"rel_{digest}"


def merge_relationships(rels: List[Relationship]) -> List[Relationship]:
    """
    Collapse duplicates onto (source, type, target), unioning their evidence.

    The same relationship discovered by the chunk stage and again by the
    cross-chunk stage must become one edge with two evidence records, not two
    parallel edges — otherwise the graph double-counts and provenance
    fragments.
    """
    merged: Dict[str, Relationship] = {}
    for r in rels:
        key = relationship_key(r.source_concept_id, r.type, r.target_concept_id)
        if key not in merged:
            merged[key] = r
            continue
        existing = merged[key]
        seen = {(norm(e.text), e.chunk_id) for e in existing.evidence}
        for e in r.evidence:
            if (norm(e.text), e.chunk_id) not in seen:
                existing.evidence.append(e)
                seen.add((norm(e.text), e.chunk_id))
    return list(merged.values())


def relationship_to_dict(r: Relationship) -> Dict[str, Any]:
    return {
        "relationship_id": r.relationship_id,
        "source_concept_id": r.source_concept_id,
        "source_name": r.source_name,
        "target_concept_id": r.target_concept_id,
        "target_name": r.target_name,
        "type": r.type,
        "resource_id": r.resource_id,
        "occurrence_count": r.occurrence_count,
        "mean_confidence": r.mean_confidence,
        "chunk_ids": r.chunk_ids,
        "evidence": [vars(e) for e in r.evidence],
    }


def relationship_from_dict(d: Dict[str, Any]) -> Relationship:
    return Relationship(
        relationship_id=d["relationship_id"],
        source_concept_id=d["source_concept_id"],
        source_name=d.get("source_name", ""),
        target_concept_id=d["target_concept_id"],
        target_name=d.get("target_name", ""),
        type=d["type"],
        resource_id=d.get("resource_id", ""),
        evidence=[EvidenceRecord(**e) for e in d.get("evidence", [])],
    )

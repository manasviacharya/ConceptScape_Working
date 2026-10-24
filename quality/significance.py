import re
from typing import Any, Dict, Iterable, Tuple


_LABEL_WORDS = re.compile(r"\b(table|figure|slide|step|iteration|epoch|row|column|output|input)\b", re.I)
_NUMBER_FRAGMENT = re.compile(r"(?:^|\s)[-+]?\d+(?:\.\d+)?(?:%|\b)")


def significance_assessment(concept: Dict[str, Any]) -> Dict[str, Any]:
    """Score pedagogical value without changing or discarding provenance."""
    name = str(concept.get("canonical_name") or "").strip()
    definition = str(concept.get("definition") or "").strip()
    evidence = " ".join(str(item) for item in concept.get("evidence", []))
    score = 0.45
    reasons = []
    if len(definition) >= 40:
        score += 0.22
    else:
        reasons.append("short_definition")
    if len(concept.get("keywords", [])) >= 2:
        score += 0.12
    if int(concept.get("occurrence_count", 0) or 0) > 1:
        score += 0.12
    if _LABEL_WORDS.search(name):
        score -= 0.28; reasons.append("table_or_layout_label")
    if _NUMBER_FRAGMENT.search(name) or (definition and len(_NUMBER_FRAGMENT.findall(definition)) >= 2):
        score -= 0.25; reasons.append("worked_numeric_fragment")
    if len(name.split()) <= 2 and len(definition) < 30:
        score -= 0.12; reasons.append("underspecified_fragment")
    if not evidence:
        score -= 0.35; reasons.append("missing_evidence")
    score = max(0.0, min(1.0, round(score, 3)))
    status = "include" if score >= 0.5 else "review" if score >= 0.3 else "exclude"
    return {"significance_score": score, "significance_status": status, "significance_reasons": reasons}


def filter_concepts(concepts: Iterable[Dict[str, Any]]) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    kept, audit = [], []
    for concept in concepts:
        decision = significance_assessment(concept)
        enriched = {**concept, **decision}
        audit.append({"concept_id": concept.get("concept_id"), **decision,
                      "raw_concept": concept})
        if decision["significance_status"] != "exclude":
            kept.append(enriched)
    return kept, audit

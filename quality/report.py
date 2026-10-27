"""Workspace-safe quality inventory generation."""

import re
from pathlib import Path
from typing import Any


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}


def build_quality_report(concepts: list[dict[str, Any]], relationships: list[dict[str, Any]],
                        raw_path: str = "normalized_concepts_raw.json",
                        filtered_path: str = "normalized_concepts.json") -> dict[str, Any]:
    low_confidence = [c for c in concepts if float(c.get("mean_confidence", 1.0)) < 0.6]
    ocr_flags = [c for c in concepts if any(mark in " ".join(c.get("evidence", [])).lower()
                                             for mark in ("�", "ocr", "garbled"))]
    near_duplicates = []
    for index, left in enumerate(concepts):
        left_tokens = _tokens(left.get("canonical_name", ""))
        for right in concepts[index + 1:]:
            right_tokens = _tokens(right.get("canonical_name", ""))
            if not left_tokens or not right_tokens or left.get("concept_id") == right.get("concept_id"):
                continue
            similarity = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
            if similarity >= 0.75:
                near_duplicates.append({"left": left["concept_id"], "right": right["concept_id"],
                                        "similarity": round(similarity, 3)})
    low_confidence_edges = [r for r in relationships if float(r.get("mean_confidence", 1.0)) < 0.6]
    return {
        "concepts": {"total": len(concepts), "low_confidence": low_confidence,
                     "ocr_suspect": ocr_flags, "near_duplicates": near_duplicates},
        "relationships": {"total": len(relationships), "low_confidence": low_confidence_edges},
        "traceability": {"raw_concepts": raw_path, "filtered_concepts": filtered_path},
    }


def build_quality_report_from_dir(data_dir: Path) -> dict[str, Any]:
    import json
    with (data_dir / "normalized_concepts.json").open(encoding="utf-8") as handle:
        concepts = json.load(handle).get("concepts", [])
    with (data_dir / "relationships.json").open(encoding="utf-8") as handle:
        relationships = json.load(handle).get("relationships", [])
    return build_quality_report(concepts, relationships)

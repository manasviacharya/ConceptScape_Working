"""Create a traceable quality report without mutating graph/source artefacts."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


def tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}


concepts = load("data/normalized_concepts.json").get("concepts", [])
relationships = load("data/relationships.json").get("relationships", [])
low_confidence = [c for c in concepts if float(c.get("mean_confidence", 1.0)) < 0.6]
ocr_flags = [c for c in concepts if any(mark in " ".join(c.get("evidence", [])).lower() for mark in ("�", "ocr", "garbled"))]
near_duplicates = []
for index, left in enumerate(concepts):
    for right in concepts[index + 1:]:
        a, b = tokens(left.get("canonical_name", "")), tokens(right.get("canonical_name", ""))
        if a and b and len(a & b) / len(a | b) >= 0.75 and left["concept_id"] != right["concept_id"]:
            near_duplicates.append({"left": left["concept_id"], "right": right["concept_id"], "similarity": round(len(a & b) / len(a | b), 3)})
low_confidence_edges = [r for r in relationships if float(r.get("mean_confidence", 1.0)) < 0.6]
report = {"concepts": {"total": len(concepts), "low_confidence": low_confidence, "ocr_suspect": ocr_flags, "near_duplicates": near_duplicates},
          "relationships": {"total": len(relationships), "low_confidence": low_confidence_edges},
          "traceability": {"raw_concepts": "data/normalized_concepts_raw.json", "filtered_concepts": "data/normalized_concepts.json"}}
(ROOT / "data").mkdir(exist_ok=True)
with (ROOT / "data/quality_report.json").open("w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, ensure_ascii=False)
print("Quality report written to data/quality_report.json")

"""Prepare/score human-labelled pedagogical significance review sheets.

Examples (run later, after implementation review):
  python scripts/significance_review.py --prepare
  python scripts/significance_review.py --score
"""
import argparse
import json
from pathlib import Path

from evaluation.significance import precision_recall_f1

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "evaluation" / "significance_review.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        source = ROOT / "data" / "normalized_concepts_raw.json"
        if not source.exists():
            raise SystemExit("Run the normalization pipeline before preparing a review sheet.")
        concepts = json.loads(source.read_text(encoding="utf-8")).get("concepts", [])
        filtered = {item["concept_id"]: item for item in json.loads((ROOT / "data" / "normalized_concepts.json").read_text(encoding="utf-8")).get("concepts", [])}
        previous = {}
        if SHEET.exists():
            previous = {item["concept_id"]: item for item in json.loads(SHEET.read_text(encoding="utf-8")).get("items", [])}
        items = []
        for concept in concepts:
            old = previous.get(concept["concept_id"], {})
            items.append({"concept_id": concept["concept_id"], "name": concept.get("canonical_name"),
                          "evidence": concept.get("evidence", []),
                          "predicted": "include" if concept["concept_id"] in filtered else "exclude",
                          "gold": old.get("gold", ""), "note": old.get("note", "")})
        SHEET.parent.mkdir(exist_ok=True)
        SHEET.write_text(json.dumps({"instructions": "Label gold as include or exclude; leave ambiguous items blank and report them.", "items": items}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Review sheet written to {SHEET}")
    if args.score:
        if not SHEET.exists():
            raise SystemExit("No review sheet. Run with --prepare first.")
        items = json.loads(SHEET.read_text(encoding="utf-8")).get("items", [])
        print(json.dumps(precision_recall_f1(items), indent=2))


if __name__ == "__main__":
    main()

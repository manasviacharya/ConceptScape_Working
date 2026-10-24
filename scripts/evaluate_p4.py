"""Build one honest P4 report from available labels and quality artefacts.

Missing human labels are reported as pending; no metric is fabricated.
"""
import json
from pathlib import Path

from evaluation.rag_quality import score_answers
from evaluation.significance import precision_recall_f1

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


significance = read_json(ROOT / "evaluation" / "significance_review.json", {"items": []})
rag = read_json(ROOT / "evaluation" / "rag_labels.json", {"items": []})
quality = read_json(ROOT / "data" / "quality_report.json", {})
report = {
    "significance": precision_recall_f1(significance.get("items", [])),
    "rag": score_answers(rag.get("items", [])),
    "quality_inventory": {
        "low_confidence_concepts": len(quality.get("concepts", {}).get("low_confidence", [])),
        "ocr_suspect_concepts": len(quality.get("concepts", {}).get("ocr_suspect", [])),
        "near_duplicate_pairs": len(quality.get("concepts", {}).get("near_duplicates", [])),
        "low_confidence_relationships": len(quality.get("relationships", {}).get("low_confidence", [])),
    },
    "status": "complete" if significance.get("items") and rag.get("items") else "pending_human_labels",
}
(ROOT / "evaluation" / "p4_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("P4 report written to evaluation/p4_report.json")

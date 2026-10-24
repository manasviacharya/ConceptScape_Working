"""Metrics for human-labelled grounded-answer/citation review sheets."""
from typing import Any, Dict, Iterable


def score_answers(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [row for row in rows if row.get("gold_citations") is not None]
    if not rows:
        return {"labelled": 0, "citation_precision": None, "citation_recall": None, "citation_f1": None, "grounded_rate": None}
    tp = fp = fn = grounded = 0
    for row in rows:
        gold = set(row.get("gold_citations", [])); used = set(row.get("used_citations", []))
        tp += len(gold & used); fp += len(used - gold); fn += len(gold - used)
        grounded += int(row.get("answer_supported", False) and row.get("citation_valid", False))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"labelled": len(rows), "citation_precision": round(precision, 4), "citation_recall": round(recall, 4),
            "citation_f1": round(f1, 4), "grounded_rate": round(grounded / len(rows), 4)}

"""Score human-labelled include/exclude judgements honestly."""
from typing import Any, Dict, Iterable


def precision_recall_f1(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    judged = [item for item in items if item.get("gold") in {"include", "exclude"}]
    if not judged:
        return {"judged": 0, "precision": None, "recall": None, "f1": None}
    predicted = [item.get("predicted") == "include" for item in judged]
    gold = [item.get("gold") == "include" for item in judged]
    tp = sum(p and g for p, g in zip(predicted, gold))
    fp = sum(p and not g for p, g in zip(predicted, gold))
    fn = sum(not p and g for p, g in zip(predicted, gold))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"judged": len(judged), "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}

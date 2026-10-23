import json
import os
import random
from typing import Any, Dict, List

REVIEW_DIR = os.path.join("evaluation", "reviews")

# Every review sheet uses the same verdict vocabulary so the scoring code is
# shared. "unsure" is deliberate: forcing a binary judgement on a genuinely
# ambiguous item produces a number that looks more certain than the underlying
# data, and those items are worth reporting separately.
VERDICTS = ("correct", "incorrect", "unsure")


def sheet_path(name: str) -> str:
    return os.path.join(REVIEW_DIR, f"{name}.json")


def write_sheet(name: str, items: List[Dict[str, Any]], instructions: List[str]) -> str:
    """
    Write a review sheet, preserving any verdicts already recorded.

    Re-running the sampler must not discard work: an item already judged keeps
    its verdict and note, matched on its id.
    """
    os.makedirs(REVIEW_DIR, exist_ok=True)
    path = sheet_path(name)

    previous: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for it in json.load(f).get("items", []):
                if it.get("verdict"):
                    previous[it["id"]] = it

    for it in items:
        prior = previous.get(it["id"])
        it["verdict"] = prior.get("verdict", "") if prior else ""
        it["note"] = prior.get("note", "") if prior else ""

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "_instructions": instructions,
            "_verdicts": list(VERDICTS),
            "reviewed": sum(1 for i in items if i["verdict"]),
            "total": len(items),
            "items": items,
        }, f, indent=2, ensure_ascii=False)
    return path


def load_sheet(name: str) -> List[Dict[str, Any]]:
    path = sheet_path(name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No review sheet at {path}. Run with --prepare first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("items", [])


def score(items: List[Dict[str, Any]], group_by: str = "") -> Dict[str, Any]:
    """
    Precision over judged items, optionally broken down by a field.

    Unjudged and "unsure" items are excluded from the denominator and reported
    separately — counting them either way would misstate precision.
    """
    judged = [i for i in items if i.get("verdict") in ("correct", "incorrect")]
    unsure = [i for i in items if i.get("verdict") == "unsure"]
    pending = [i for i in items if not i.get("verdict")]

    def precision(subset):
        if not subset:
            return None
        return round(sum(1 for i in subset if i["verdict"] == "correct") / len(subset), 3)

    result = {
        "total": len(items),
        "judged": len(judged),
        "unsure": len(unsure),
        "pending": len(pending),
        "correct": sum(1 for i in judged if i["verdict"] == "correct"),
        "precision": precision(judged),
    }

    if group_by:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for i in judged:
            groups.setdefault(str(i.get(group_by, "")), []).append(i)
        result["by_" + group_by] = {
            k: {"n": len(v), "precision": precision(v)}
            for k, v in sorted(groups.items())
        }
    return result


def print_report(title: str, result: Dict[str, Any], group_by: str = "") -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if result["pending"]:
        print(f"  {result['pending']} of {result['total']} items still unjudged — "
              f"precision below is provisional")
    print(f"  judged     : {result['judged']}  (correct {result['correct']}, "
          f"incorrect {result['judged'] - result['correct']})")
    if result["unsure"]:
        print(f"  unsure     : {result['unsure']}  (excluded from precision)")
    p = result["precision"]
    print(f"  precision  : {p if p is not None else 'n/a — nothing judged yet'}")

    key = "by_" + group_by
    if group_by and result.get(key):
        print(f"\n  by {group_by}:")
        for k, v in result[key].items():
            print(f"    {k:<22} n={v['n']:<4} precision={v['precision']}")


def sample(items: List[Any], n: int, seed: int = 42) -> List[Any]:
    """Reproducible sample — a fixed seed means the reported set can be re-derived."""
    if len(items) <= n:
        return list(items)
    rng = random.Random(seed)
    return rng.sample(list(items), n)

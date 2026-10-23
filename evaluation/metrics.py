from typing import Dict, List, Sequence


def precision_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Fraction of the top-k results that are relevant."""
    if k <= 0:
        return 0.0
    top = list(retrieved)[:k]
    if not top:
        return 0.0
    hits = sum(1 for r in top if r in set(relevant))
    # Divided by len(top), not k: with fewer than k results, dividing by k would
    # penalise a retriever for the corpus being small rather than for ranking badly.
    return hits / len(top)


def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Fraction of all relevant items that appear in the top k."""
    rel = set(relevant)
    if not rel:
        return 0.0
    return sum(1 for r in list(retrieved)[:k] if r in rel) / len(rel)


def reciprocal_rank(retrieved: Sequence[str], relevant: Sequence[str]) -> float:
    """
    1 / rank of the first relevant result, else 0.

    Rewards putting a correct answer first rather than merely somewhere in the
    list — which is what matters when the result feeds a generated answer that
    only reads the top few citations.
    """
    rel = set(relevant)
    for i, r in enumerate(retrieved, start=1):
        if r in rel:
            return 1.0 / i
    return 0.0


def hit_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """1.0 if any relevant item is in the top k."""
    rel = set(relevant)
    return 1.0 if any(r in rel for r in list(retrieved)[:k]) else 0.0


def summarise(per_query: List[Dict[str, float]]) -> Dict[str, float]:
    """Macro-average each metric across queries; every query weighs the same."""
    if not per_query:
        return {}
    keys = per_query[0].keys()
    return {k: round(sum(q[k] for q in per_query) / len(per_query), 4) for k in keys}

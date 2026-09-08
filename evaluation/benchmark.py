import json
import logging
import os
from typing import Any, Dict, List, Optional

from config import settings
from evaluation.metrics import hit_at_k, precision_at_k, recall_at_k, reciprocal_rank, summarise

RETRIEVER_ORDER = ["keyword", "semantic", "graph", "hybrid"]


def load_cases(path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = path or os.path.join("evaluation", "queries.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("cases", [])


def _norm(s: str) -> str:
    return " ".join((s or "").split()).casefold()


def resolve_cases(
    cases: List[Dict[str, Any]], concepts: List[Dict[str, Any]]
) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Turn ground-truth entries into concept_ids, accepting names or ids.

    Ground truth is written using concept NAMES because concept_ids are
    derived from the match key and are reassigned every time normalization
    changes — enabling semantic fusion, for instance, rewrites all of them.
    Name-based cases survive that; id-based ones would silently score zero for
    every retriever and look like a retrieval collapse rather than a stale
    fixture. Ids are still accepted so existing cases keep working.
    """
    by_id = {c["concept_id"] for c in concepts}
    by_name: Dict[str, str] = {}
    for c in concepts:
        by_name.setdefault(_norm(c.get("canonical_name", "")), c["concept_id"])
        for alias in c.get("aliases", []):
            by_name.setdefault(_norm(alias), c["concept_id"])

    resolved, problems = [], []
    for case in cases:
        ids, unresolved = [], []
        for ref in case.get("relevant", []):
            if ref in by_id:
                ids.append(ref)
            elif _norm(ref) in by_name:
                ids.append(by_name[_norm(ref)])
            else:
                unresolved.append(ref)
        if unresolved:
            problems.append(f"{case['id']} ({case['query'][:44]}…): no concept matches {unresolved}")
        resolved.append({**case, "relevant": ids})
    return resolved, problems


def evaluate(
    retrievers: Dict[str, Any],
    cases: List[Dict[str, Any]],
    k_values: List[int] = None,
    top_k: int = None,
) -> Dict[str, Any]:
    """
    Run every retriever over every case and score the rankings.

    Only concept results are scored. Chunk hits are legitimate retrieval output
    but the ground truth is expressed in concepts, so counting chunks would
    penalise the retrievers that surface them.
    """
    k_values = k_values or [1, 3, 5]
    top_k = top_k or max(k_values) * 2

    per_retriever: Dict[str, Any] = {}

    for name in RETRIEVER_ORDER:
        retriever = retrievers.get(name)
        if retriever is None:
            logging.warning(f"{name} retriever unavailable — skipped")
            continue

        rows, per_query = [], []
        for case in cases:
            try:
                results = retriever.retrieve(case["query"], top_k)
            except Exception as e:
                logging.error(f"{name} failed on {case['id']}: {e}")
                results = []

            ranked = [r.id for r in results if r.kind == "concept"]
            relevant = case.get("relevant", [])

            scores: Dict[str, float] = {}
            for k in k_values:
                scores[f"P@{k}"] = precision_at_k(ranked, relevant, k)
                scores[f"R@{k}"] = recall_at_k(ranked, relevant, k)
                scores[f"Hit@{k}"] = hit_at_k(ranked, relevant, k)
            scores["MRR"] = reciprocal_rank(ranked, relevant)

            per_query.append(scores)
            rows.append({
                "id": case["id"],
                "query": case["query"],
                "type": case.get("type", ""),
                "kind": case.get("kind", ""),
                "relevant": relevant,
                "retrieved": ranked[:max(k_values)],
                **{k: round(v, 4) for k, v in scores.items()},
            })

        per_retriever[name] = {"overall": summarise(per_query), "per_query": rows}

    # A per-kind breakdown is where the interesting result lives: lexical
    # matching does fine on direct lookups and collapses on paraphrases.
    by_kind: Dict[str, Dict[str, Dict[str, float]]] = {}
    for kind in sorted({c.get("kind", "") for c in cases}):
        ids = {c["id"] for c in cases if c.get("kind") == kind}
        by_kind[kind] = {
            name: summarise([r for r in data["per_query"] if r["id"] in ids] and
                            [{m: r[m] for m in data["overall"]} for r in data["per_query"] if r["id"] in ids])
            for name, data in per_retriever.items()
        }

    return {
        "cases": len(cases),
        "k_values": k_values,
        "retrievers": per_retriever,
        "by_kind": by_kind,
    }

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from config import settings


def _tokens(s: str) -> set:
    return {t for t in re.split(r"[^\w]+", (s or "").casefold()) if len(t) > 2}


def _fusion_text(concept) -> str:
    """
    What gets embedded when deciding whether two concepts are the same.

    Name plus definition — deliberately NOT the evidence spans. Evidence is
    source text that two genuinely different concepts often share (they appear
    on the same slide), which would make unrelated concepts look similar.
    Retrieval embeddings include evidence because there the goal is recall;
    here the goal is precision, and a wrong merge is unrecoverable.
    """
    parts = [concept.canonical_name]
    if concept.definition:
        parts.append(concept.definition)
    return " — ".join(p for p in parts if p)


def _word_seq(s: str) -> List[str]:
    return [t for t in re.split(r"[^\w]+", (s or "").casefold()) if t]


def _expand_initialisms(short: List[str], long: List[str]) -> List[str]:
    """
    Replace an initialism in `short` with the words it abbreviates in `long`.

    "SGD" against "stochastic gradient descent" expands to those three words,
    because S-G-D are their initials. This is derived from the two names being
    compared rather than from a hardcoded dictionary, so it cannot invent an
    expansion the corpus does not support.
    """
    out: List[str] = []
    for tok in short:
        if not (2 <= len(tok) <= 6 and tok.isalpha()):
            out.append(tok)
            continue
        n = len(tok)
        match = next(
            (long[i:i + n] for i in range(len(long) - n + 1)
             if "".join(w[0] for w in long[i:i + n]) == tok),
            None,
        )
        out.extend(match if match else [tok])
    return out


def _compatible(a, b) -> Tuple[bool, str]:
    """
    Guards applied before any merge, regardless of similarity.

    Deliberately conservative, because the two error types are not symmetric: a
    missed merge leaves two nodes that a later pass can still join, while a
    wrong merge destroys both concepts irrecoverably.

    The dangerous case is a strict token subset. "Batch Gradient Descent" is a
    subset of "Mini-Batch Stochastic Gradient Descent", yet they are different
    algorithms — the extra words are exactly what distinguishes them. Subset
    alone is therefore never sufficient.
    """
    wa, wb = _word_seq(a.canonical_name), _word_seq(b.canonical_name)
    if not wa or not wb:
        return False, "no comparable tokens"

    # Same phrase once abbreviations are expanded — the safe merge.
    # "Mini-Batch SGD" == "Mini-Batch Stochastic Gradient Descent".
    ea = set(_expand_initialisms(wa, wb))
    eb = set(_expand_initialisms(wb, wa))
    if ea == eb:
        return True, "same phrase after expanding abbreviations"

    # Otherwise require one name to be a substring of the other AND the extra
    # text to be non-discriminating — a qualifier or notation, not a modifier
    # that names a different variant.
    na, nb = a.canonical_name.casefold().strip(), b.canonical_name.casefold().strip()
    if na in nb or nb in na:
        extra = (eb - ea) or (ea - eb)
        if not extra & _DISCRIMINATORS:
            return True, "one name contains the other, no distinguishing modifier"
        return False, f"contains, but differs by {sorted(extra & _DISCRIMINATORS)}"

    return False, f"names differ: {sorted(ea ^ eb)[:4]}"


# Words that name a *variant* rather than qualify the same thing. Two concepts
# differing by one of these are different concepts, however similar the text:
# batch / stochastic / mini-batch gradient descent are three algorithms.
_DISCRIMINATORS = {
    "mini", "batch", "stochastic", "global", "local", "simple", "steepest",
    "random", "first", "second", "initial", "final", "maximum", "minimum",
}


def fuse(
    concepts: List[Any],
    embedder=None,
    threshold: Optional[float] = None,
) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """
    Merge concepts that are semantically the same but lexically different.

    Lexical normalization already handles case, plurals, parentheticals and
    corpus-learned abbreviations. What it cannot bridge is a full expansion:
    "Mini-Batch SGD" and "Mini-Batch Stochastic Gradient Descent" share a match
    key with neither. Embedding similarity can — but only behind the guards
    above, because the failure mode is silent and destructive.

    Returns (fused_concepts, decisions) where decisions records BOTH merges and
    refusals. The refusals are a result in their own right: a pair scoring high
    similarity that the guards held apart is the guard design working, and it is
    the half of the evaluation that shows the method is not merely permissive.
    """
    threshold = threshold if threshold is not None else settings.fusion_similarity_threshold
    if len(concepts) < 2:
        return concepts, []

    if embedder is None:
        from retrieval.embedder import Embedder
        embedder = Embedder()

    logging.info(f"Semantic fusion: embedding {len(concepts)} concepts (threshold {threshold})")
    vectors = embedder.encode([_fusion_text(c) for c in concepts])

    # Union-find: merging A into B and B into C must put all three together.
    parent = list(range(len(concepts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    merge_log: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            # Vectors are normalised at encode time, so the dot product is cosine.
            sim = sum(a * b for a, b in zip(vectors[i], vectors[j]))
            if sim < threshold:
                continue
            ok, reason = _compatible(concepts[i], concepts[j])
            entry = {
                "a": concepts[i].canonical_name,
                "b": concepts[j].canonical_name,
                "similarity": round(sim, 4),
                "reason": reason,
            }
            if ok:
                union(i, j)
                merge_log.append(entry)
            else:
                rejected.append(entry)

    for r in rejected:
        logging.info(f"  held apart ({r['similarity']}): {r['a']!r} / {r['b']!r} — {r['reason']}")
    for m in merge_log:
        logging.info(f"  MERGE ({m['similarity']}): {m['a']!r} + {m['b']!r} — {m['reason']}")

    groups: Dict[int, List[int]] = {}
    for i in range(len(concepts)):
        groups.setdefault(find(i), []).append(i)

    fused = [
        concepts[idx[0]] if len(idx) == 1 else _merge_group([concepts[i] for i in idx])
        for idx in groups.values()
    ]
    logging.info(f"Semantic fusion: {len(concepts)} -> {len(fused)} concepts "
                 f"({len(merge_log)} merges, {len(rejected)} held apart)")
    decisions = ([{**m, "decision": "merged"} for m in merge_log] +
                 [{**r, "decision": "held_apart"} for r in rejected])
    return fused, decisions


def _merge_group(group: List[Any]) -> Any:
    """
    Combine concepts into one, keeping every source.

    Canonical name is the most-mentioned, ties to the longest — the longer form
    usually carries the expansion rather than the abbreviation. Provenance is
    unioned exactly as in lexical merging: losing a source here would break the
    citation chain.
    """
    from dataclasses import replace

    primary = max(group, key=lambda c: (c.occurrence_count, len(c.canonical_name)))

    def union_list(attr: str) -> List[Any]:
        seen, out = set(), []
        for c in group:
            for v in getattr(c, attr, []) or []:
                if v not in seen:
                    seen.add(v)
                    out.append(v)
        return out

    names = union_list("aliases") or [c.canonical_name for c in group]
    total = sum(c.occurrence_count for c in group)
    weighted = sum(c.mean_confidence * c.occurrence_count for c in group)

    return replace(
        primary,
        canonical_name=primary.canonical_name,
        aliases=sorted({*names, *(c.canonical_name for c in group)}),
        keywords=sorted(set(union_list("keywords"))),
        mention_ids=union_list("mention_ids"),
        chunk_ids=union_list("chunk_ids"),
        filenames=union_list("filenames"),
        page_numbers=sorted(set(union_list("page_numbers"))),
        evidence=union_list("evidence"),
        resource_ids=sorted(set(union_list("resource_ids"))),
        models_used=sorted(set(union_list("models_used"))),
        occurrence_count=total,
        mean_confidence=round(weighted / total, 3) if total else 0.0,
    )

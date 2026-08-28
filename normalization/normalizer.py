import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List

from config import settings
from normalization.models import CanonicalConcept

# Trailing parenthetical: "Stochastic Gradient Descent (SGD)" -> drop "(SGD)".
# Also catches notation like "Learning rate (η)".
_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")

# Leading/trailing punctuation and stray symbols that carry no meaning.
_EDGE_JUNK = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)

# Plural folding is deliberately rule-based rather than a lemmatiser: adding
# spaCy or NLTK for this would pull a heavy dependency and a model download
# for a transformation that is four rules wide on technical noun phrases.
_IRREGULAR = {"analyses": "analysis", "bases": "basis", "hypotheses": "hypothesis"}


def _fold_plural(word: str) -> str:
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("sses"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def match_key(name: str) -> str:
    """
    Reduce a surface form to the key that decides whether two mentions merge.

    Only the LAST word is plural-folded: "Neural Networks" -> "neural network",
    while "Gradient Descent Variants" keeps its internal words intact.
    """
    s = unicodedata.normalize("NFKC", name or "")

    if settings.normalize_strip_parentheticals:
        s = _TRAILING_PAREN.sub("", s)

    s = re.sub(r"\s+", " ", s).strip().casefold()
    s = _EDGE_JUNK.sub("", s)

    if settings.normalize_fold_plurals and s:
        parts = s.split(" ")
        parts[-1] = _fold_plural(parts[-1])
        s = " ".join(parts)

    return s


def _pick_canonical_name(names: List[str]) -> str:
    """
    Most frequent surface form wins; ties break toward the longest, since the
    longer form usually carries the expansion ("... (SGD)") rather than losing it.
    """
    counts = Counter(names)
    top = max(counts.values())
    return max((n for n, c in counts.items() if c == top), key=len)


def _pick_definition(mentions: List[Dict[str, Any]]) -> str:
    """
    Highest confidence wins; ties break toward the longest definition.

    Definitions are never concatenated — stitching several together produces
    text that no single source ever stated, which breaks grounding.
    """
    best = max(
        mentions,
        key=lambda m: (float(m.get("confidence") or 0.0), len(m.get("definition") or "")),
    )
    return best.get("definition", "")


def _dedupe(values: List[Any]) -> List[Any]:
    seen, out = set(), []
    for v in values:
        if v not in seen and v not in ("", None):
            seen.add(v)
            out.append(v)
    return out


def normalize(mentions: List[Dict[str, Any]]) -> List[CanonicalConcept]:
    """Merge mentions into canonical concepts, scoped within each document."""
    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

    for m in mentions:
        resource_id = (m.get("source_reference") or {}).get("resource_id", "")
        key = match_key(m.get("concept_name", ""))
        if not key:
            continue
        groups[(resource_id, key)].append(m)

    concepts: List[CanonicalConcept] = []

    for (resource_id, key), group in sorted(groups.items()):
        names = [m.get("concept_name", "") for m in group]
        confidences = [float(m.get("confidence") or 0.0) for m in group]
        canonical = _pick_canonical_name(names)

        pages = []
        for m in group:
            src = m.get("source_reference") or {}
            n = src.get("page_number", src.get("slide_number"))
            if isinstance(n, int):
                pages.append(n)

        digest = hashlib.sha256(f"{resource_id}:{key}".encode("utf-8")).hexdigest()[:12]

        concepts.append(CanonicalConcept(
            concept_id=f"concept_{digest}",
            canonical_name=canonical,
            resource_id=resource_id,
            definition=_pick_definition(group),
            aliases=sorted(_dedupe(names)),
            keywords=sorted(_dedupe([k for m in group for k in (m.get("keywords") or [])])),
            mention_ids=[m.get("concept_id", "") for m in group],
            chunk_ids=_dedupe([(m.get("source_reference") or {}).get("chunk_id", "") for m in group]),
            filenames=_dedupe([(m.get("source_reference") or {}).get("filename", "") for m in group]),
            page_numbers=sorted(set(pages)),
            evidence=_dedupe([m.get("evidence", "") for m in group]),
            occurrence_count=len(group),
            mean_confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            models_used=sorted(_dedupe([m.get("model_used", "") for m in group])),
        ))

    return concepts

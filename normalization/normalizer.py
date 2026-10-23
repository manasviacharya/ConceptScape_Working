import hashlib
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

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


def build_abbreviation_map(names: List[str]) -> Dict[str, str]:
    """
    Learn abbreviations from the corpus itself, e.g. "Stochastic Gradient
    Descent (SGD)" teaches SGD -> "stochastic gradient descent".

    Derived from the documents rather than hardcoded, so it never invents an
    expansion the source material does not actually state. Only short, mostly
    uppercase parentheticals qualify — that excludes qualifiers like
    "Gradient (batch)" and symbols like "Learning rate (η)", which are
    disambiguators, not abbreviations.
    """
    mapping: Dict[str, str] = {}
    for name in names:
        m = re.search(r"^(.*?)\s*\(([^)]{1,6})\)\s*$", name or "")
        if not m:
            continue
        long_form, abbr = m.group(1).strip(), m.group(2).strip()
        if not long_form or not abbr.isalpha():
            continue
        # Require it to look like an initialism, not a lowercase qualifier.
        if not (abbr.isupper() and len(abbr) >= 2):
            continue
        mapping.setdefault(abbr.casefold(), _basic_key(long_form))
    return mapping


def _basic_key(name: str) -> str:
    """Canonicalisation shared by match_key and the abbreviation map."""
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


def _expand_abbreviations(key: str, abbrev: Dict[str, str]) -> str:
    """
    Expand abbreviation tokens using the corpus-derived map.

    Handles the whole name being an abbreviation ("SGD") and an abbreviation
    used as part of a longer name ("Stochastic GD"), which is why expansion is
    per-token rather than whole-string.
    """
    if not abbrev or not key:
        return key
    if key in abbrev:
        return abbrev[key]
    tokens = key.split(" ")
    if len(tokens) > 1:
        expanded, changed = [], False
        for t in tokens:
            if t in abbrev:
                expanded.extend(abbrev[t].split(" "))
                changed = True
            else:
                expanded.append(t)
        if changed:
            # Collapse repeats introduced by expansion, e.g.
            # "stochastic" + "gradient descent" from "Stochastic GD".
            seen, out = set(), []
            for t in expanded:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
            return " ".join(out)
    return key


def match_key(name: str, abbrev: Optional[Dict[str, str]] = None) -> str:
    """
    Reduce a surface form to the key that decides whether two mentions merge.

    Only the LAST word is plural-folded: "Neural Networks" -> "neural network",
    while "Gradient Descent Variants" keeps its internal words intact.
    """
    key = _basic_key(name)
    if abbrev:
        key = _expand_abbreviations(key, abbrev)
    return key


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


def _dedupe_locations(locations: List[dict]) -> List[dict]:
    seen, out = set(), []
    for loc in locations:
        key = (loc["type"], loc["number"], loc["filename"])
        if key not in seen:
            seen.add(key)
            out.append(loc)
    return sorted(out, key=lambda l: (l["filename"], l["number"]))


def _dedupe(values: List[Any]) -> List[Any]:
    seen, out = set(), []
    for v in values:
        if v not in seen and v not in ("", None):
            seen.add(v)
            out.append(v)
    return out


def normalize(mentions: List[Dict[str, Any]], cross_document: bool = None) -> List[CanonicalConcept]:
    """
    Merge mentions into canonical concepts.

    With cross_document enabled the group key is the match key alone, so the
    same concept taught in several documents becomes ONE node carrying every
    source. Scoping to a single document instead leaves duplicates that
    fragment the graph and crowd out retrieval results.
    """
    if cross_document is None:
        cross_document = settings.normalize_cross_document

    abbrev = build_abbreviation_map([m.get("concept_name", "") for m in mentions])
    if abbrev:
        logging.info(f"Learned {len(abbrev)} abbreviation(s) from the corpus: "
                     + ", ".join(f"{k.upper()}->{v}" for k, v in sorted(abbrev.items())))

    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

    for m in mentions:
        resource_id = (m.get("source_reference") or {}).get("resource_id", "")
        key = match_key(m.get("concept_name", ""), abbrev)
        if not key:
            continue
        groups[(key,) if cross_document else (resource_id, key)].append(m)

    concepts: List[CanonicalConcept] = []

    for group_key, group in sorted(groups.items()):
        key = group_key[-1]
        names = [m.get("concept_name", "") for m in group]
        confidences = [float(m.get("confidence") or 0.0) for m in group]
        canonical = _pick_canonical_name(names)

        # Positions are collected from the generic location_number, falling back
        # to the typed aliases for mentions extracted before that field existed.
        # Reading only page_number/slide_number silently dropped the position of
        # every source measured in anything else — a video timestamp, say.
        pages, locations = [], []
        for m in group:
            src = m.get("source_reference") or {}
            n = src.get("location_number")
            if n is None:
                n = src.get("page_number", src.get("slide_number", src.get("timestamp_seconds")))
            if isinstance(n, int):
                pages.append(n)
                locations.append({
                    "type": src.get("location_type", ""),
                    "number": n,
                    "filename": src.get("filename", ""),
                })

        resource_ids = _dedupe([(m.get("source_reference") or {}).get("resource_id", "") for m in group])
        digest = hashlib.sha256(
            (key if cross_document else f"{resource_ids[0] if resource_ids else ''}:{key}").encode("utf-8")
        ).hexdigest()[:12]

        concepts.append(CanonicalConcept(
            concept_id=f"concept_{digest}",
            canonical_name=canonical,
            resource_ids=sorted(resource_ids),
            definition=_pick_definition(group),
            aliases=sorted(_dedupe(names)),
            keywords=sorted(_dedupe([k for m in group for k in (m.get("keywords") or [])])),
            mention_ids=[m.get("concept_id", "") for m in group],
            chunk_ids=_dedupe([(m.get("source_reference") or {}).get("chunk_id", "") for m in group]),
            filenames=_dedupe([(m.get("source_reference") or {}).get("filename", "") for m in group]),
            page_numbers=sorted(set(pages)),
            locations=_dedupe_locations(locations),
            evidence=_dedupe([m.get("evidence", "") for m in group]),
            occurrence_count=len(group),
            mean_confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            models_used=sorted(_dedupe([m.get("model_used", "") for m in group])),
        ))

    return concepts

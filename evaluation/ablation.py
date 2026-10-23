import json
import logging
import os
import shutil
from typing import Any, Dict, List

from config import settings

# Each variant disables exactly one contribution. `needs_extraction` marks the
# ones that change what the LLM is asked or what is kept from its answer — those
# must re-run extraction and cost quota. The rest only change post-processing and
# are free, because they reuse the baseline's extracted mentions.
VARIANTS: List[Dict[str, Any]] = [
    {
        "name": "full",
        "label": "Full system",
        "overrides": {},
        "needs_extraction": True,
    },
    {
        "name": "no_grounding",
        "label": "− evidence grounding (conventional prompt)",
        "overrides": {"extraction_grounded_prompt": False, "require_evidence": False},
        "needs_extraction": True,
    },
    {
        "name": "no_verification",
        "label": "− verification only (grounded prompt kept)",
        "overrides": {"require_evidence": False},
        "needs_extraction": True,
    },
    {
        "name": "no_fusion",
        "label": "− semantic fusion",
        "overrides": {"fusion_enabled": False},
        "needs_extraction": False,
    },
    {
        "name": "no_cross_document",
        "label": "− cross-document merging",
        "overrides": {"normalize_cross_document": False},
        "needs_extraction": False,
    },
]


class variant_settings:
    """Apply config overrides for the duration of one variant, then restore."""

    def __init__(self, overrides: Dict[str, Any], data_dir: str, output_dir: str = ""):
        self.overrides = {**overrides, "data_dir": data_dir}
        if output_dir:
            self.overrides["output_dir"] = output_dir
        self.previous: Dict[str, Any] = {}

    def __enter__(self):
        for k, v in self.overrides.items():
            self.previous[k] = getattr(settings, k)
            setattr(settings, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self.previous.items():
            setattr(settings, k, v)


def variant_dir(name: str) -> str:
    return os.path.join("data", "ablation", name)


# Documents used when running on a subset. Chosen for modality coverage rather
# than size: a native-text deck, an OCR'd PDF, and a video transcript — so the
# ablation still exercises every ingestion path.
SUBSET_DOCUMENTS = [
    "Stochastic Gradient Descent.pptx",
    "Hill Climbing.pdf",
    "gradient_descent.yt",
]
SUBSET_OUTPUT_DIR = os.path.join("output", "ablation_subset")


def build_subset(documents=None) -> str:
    """
    Write a chunks file containing only the chosen documents.

    A full ablation costs roughly five times the corpus in LLM calls, which free
    tiers cannot supply in one day — and a run that dies halfway produces
    partial rows that look like results. An ablation stays valid on a subset so
    long as every variant sees the SAME subset, so this trades corpus size for
    the ability to finish cleanly.
    """
    documents = documents or SUBSET_DOCUMENTS
    os.makedirs(SUBSET_OUTPUT_DIR, exist_ok=True)

    with open(os.path.join("output", "preprocessed_chunks.json"), encoding="utf-8") as f:
        data = json.load(f)

    keep = [c for c in data["chunks"] if c.get("filename") in documents]
    out = os.path.join(SUBSET_OUTPUT_DIR, "preprocessed_chunks.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({**data, "chunks": keep}, f, indent=2, ensure_ascii=False)

    logging.info(f"Ablation subset: {len(keep)} chunks from {len(documents)} documents")
    return out


def run_variant(variant: Dict[str, Any], reuse_extraction_from: str = "",
                output_dir: str = "") -> None:
    """
    Run the stages a variant needs, writing into its own data directory.

    Stages read and write through settings.data_dir, so pointing that at the
    variant's folder keeps each run isolated — the main pipeline outputs are
    never touched.
    """
    import run_extraction
    import run_normalization
    import run_relationships

    name = variant["name"]
    out = variant_dir(name)
    os.makedirs(out, exist_ok=True)

    with variant_settings(variant["overrides"], out, output_dir):
        if variant["needs_extraction"]:
            # Re-extract only when there is no complete extraction already. A
            # variant whose extraction finished cleanly should not pay for it
            # again just because a later stage needs re-running — that turned a
            # 10-call fix into a 150-call one.
            existing = os.path.join(out, "extracted_concepts.json")
            complete = False
            if os.path.exists(existing):
                with open(existing, encoding="utf-8") as f:
                    prior = json.load(f)
                complete = bool(prior.get("concepts")) and not prior.get("failed_chunks")

            if complete:
                logging.info(f"[{name}] extraction already complete — reusing")
            else:
                if os.path.exists(existing):
                    os.remove(existing)
                logging.info(f"[{name}] extracting (LLM calls)")
                run_extraction.main()
        else:
            src = os.path.join(variant_dir(reuse_extraction_from), "extracted_concepts.json")
            if not os.path.exists(src):
                raise RuntimeError(f"{name} needs {reuse_extraction_from}'s extraction, which is missing")
            shutil.copy(src, os.path.join(out, "extracted_concepts.json"))
            logging.info(f"[{name}] reusing extraction from '{reuse_extraction_from}' (no LLM calls)")

        logging.info(f"[{name}] normalizing")
        run_normalization.main()

        # Relationship extraction caches per chunk and per document, and remaps
        # cached edges onto whatever concept ids currently exist. Left in place,
        # a variant inherits the previous variant's edges rather than extracting
        # against its own concept set — every variant then reports an identical
        # relationship count, which looks like a finding and is an artefact.
        stale_rels = os.path.join(out, "relationships.json")
        if os.path.exists(stale_rels):
            os.remove(stale_rels)
        logging.info(f"[{name}] relationships (fresh — no inherited edges)")
        run_relationships.main()


def measure(name: str, retrievers_factory) -> Dict[str, Any]:
    """Collect the numbers that go in the paper's ablation table."""
    from evaluation.benchmark import evaluate, load_cases, resolve_cases

    out = variant_dir(name)
    with open(os.path.join(out, "extracted_concepts.json"), encoding="utf-8") as f:
        ex = json.load(f)
    with open(os.path.join(out, "normalized_concepts.json"), encoding="utf-8") as f:
        concepts = json.load(f)["concepts"]
    with open(os.path.join(out, "relationships.json"), encoding="utf-8") as f:
        rels = json.load(f)["relationships"]

    mentions = ex["concepts"]
    dropped = ex.get("dropped_concepts", [])

    # An unverifiable mention is one whose quoted evidence does not occur in the
    # source — the measurable proxy for a fabricated claim.
    unverifiable = sum(1 for m in mentions if not m.get("evidence_verified_against"))

    connected = {r["source_concept_id"] for r in rels} | {r["target_concept_id"] for r in rels}

    # A variant whose extraction or relationship pass hit a quota limit has
    # partial output that looks like a result. Flag it rather than report it:
    # a truncated row is worse than a missing one, because it invites a
    # conclusion the data does not support.
    rel_path = os.path.join(out, "relationships.json")
    with open(rel_path, encoding="utf-8") as f:
        rel_meta = json.load(f)
    incomplete = []
    if ex.get("failed_chunks"):
        incomplete.append(f"{len(ex['failed_chunks'])} chunks failed extraction")
    if rel_meta.get("failed_documents"):
        incomplete.append(f"{len(rel_meta['failed_documents'])} documents failed relationship extraction")

    result = {
        "variant": name,
        "incomplete": "; ".join(incomplete),
        "mentions": len(mentions),
        "dropped_by_verification": len(dropped),
        "unverifiable_retained": unverifiable,
        "concepts": len(concepts),
        "relationships": len(rels),
        "isolated": len(concepts) - len(connected),
        "mean_confidence": round(
            sum(float(m.get("confidence") or 0) for m in mentions) / len(mentions), 3
        ) if mentions else 0.0,
    }

    cases, _ = resolve_cases(load_cases(), concepts)
    retrievers = retrievers_factory(concepts, rels)
    scores = evaluate(retrievers, cases, [1, 3, 5])
    for retriever in ("keyword", "semantic", "graph", "hybrid"):
        overall = scores["retrievers"].get(retriever, {}).get("overall", {})
        result[f"MRR_{retriever}"] = overall.get("MRR", 0.0)
    return result

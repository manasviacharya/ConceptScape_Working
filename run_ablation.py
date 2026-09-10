"""
Ablation study: measure what each contribution actually contributes.

    python run_ablation.py                    # run everything
    python run_ablation.py --only full no_fusion
    python run_ablation.py --measure-only     # re-tabulate without re-running
    python run_ablation.py --json out.json

Variants that change the prompt or the retention rule re-run extraction and cost
LLM quota; the rest reuse the baseline's mentions and are free.
"""
import argparse
import json
import logging
import os

from config import settings
from logging_setup import configure_logging
from evaluation.ablation import VARIANTS, measure, run_variant, variant_dir


def retrievers_factory(concepts, relationships):
    from retrieval.embedder import Embedder
    from retrieval.retrievers import build_retrievers
    from retrieval.vector_store import VectorStore
    # Semantic retrieval is deliberately omitted: the vector index is built from
    # the baseline's concepts, so reusing it across variants would score each
    # variant against another's embeddings. Keyword and graph read the variant's
    # own data and are directly comparable.
    return build_retrievers(concepts, relationships, None, None)


def table(rows):
    cols = [
        ("variant", "variant", 26),
        ("mentions", "mentions", 9),
        ("dropped_by_verification", "dropped", 8),
        ("unverifiable_retained", "unverif", 8),
        ("concepts", "concepts", 9),
        ("relationships", "rels", 6),
        ("isolated", "isolated", 9),
        ("MRR_keyword", "MRR kw", 8),
        ("MRR_graph", "MRR graph", 10),
    ]
    head = "".join(f"{label:<{w}}" if k == "variant" else f"{label:>{w}}" for k, label, w in cols)
    print("\n" + head)
    print("-" * len(head))
    for r in rows:
        line = ""
        for k, _, w in cols:
            v = r.get(k, "")
            if k == "variant":
                line += f"{str(v):<{w}}"
            elif isinstance(v, float):
                line += f"{v:>{w}.3f}"
            else:
                line += f"{str(v):>{w}}"
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--measure-only", action="store_true")
    ap.add_argument("--json", dest="json_out", default="data/ablation_results.json")
    ap.add_argument("--subset", action="store_true",
                    help="run on a 3-document subset so all variants fit in one day's quota")
    args = ap.parse_args()

    configure_logging()
    logging.getLogger().setLevel(logging.WARNING)

    selected = [v for v in VARIANTS if not args.only or v["name"] in args.only]
    print(f"Variants: {', '.join(v['name'] for v in selected)}")

    output_dir = ""
    if args.subset:
        from evaluation.ablation import SUBSET_DOCUMENTS, SUBSET_OUTPUT_DIR, build_subset
        build_subset()
        output_dir = SUBSET_OUTPUT_DIR
        print(f"Subset: {', '.join(SUBSET_DOCUMENTS)}")

    if not args.measure_only:
        for v in selected:
            print(f"\n── {v['name']}: {v['label']}")
            run_variant(v, reuse_extraction_from="full", output_dir=output_dir)

    rows = []
    for v in selected:
        if not os.path.exists(os.path.join(variant_dir(v["name"]), "normalized_concepts.json")):
            print(f"  (skipping {v['name']} — not run yet)")
            continue
        rows.append({**measure(v["name"], retrievers_factory), "label": v["label"]})

    bad = [r for r in rows if r.get("incomplete")]
    if bad:
        print("\nINCOMPLETE — do not report these rows:")
        for r in bad:
            print(f"  ! {r['variant']}: {r['incomplete']}")
        print("  Re-run the affected variants once quota allows.")

    table(rows)

    base = next((r for r in rows if r["variant"] == "full"), None)
    if base and len(rows) > 1:
        print("\n\nChange versus the full system")
        print(f"{'variant':<26}{'concepts':>11}{'rels':>9}{'unverifiable':>14}")
        print("-" * 60)
        for r in rows:
            if r["variant"] == "full":
                continue
            d = lambda k: r[k] - base[k]
            print(f"{r['variant']:<26}{d('concepts'):>+11}{d('relationships'):>+9}"
                  f"{d('unverifiable_retained'):>+14}")

    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to {args.json_out}\n")


if __name__ == "__main__":
    main()

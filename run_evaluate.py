"""
Compare retrieval strategies on the ground-truth query set.

    python run_evaluate.py                 # all retrievers, default k
    python run_evaluate.py --k 1 3 5 10
    python run_evaluate.py --detail        # per-query rows
    python run_evaluate.py --json out.json # machine-readable results
"""
import argparse
import json
import logging
import os

from config import settings
from logging_setup import configure_logging
from evaluation.benchmark import RETRIEVER_ORDER, evaluate, load_cases, resolve_cases
from retrieval.embedder import Embedder
from retrieval.retrievers import build_retrievers, load_corpus
from retrieval.vector_store import VectorStore


def table(results):
    metrics = ["P@1", "P@3", "P@5", "R@3", "R@5", "Hit@3", "MRR"]
    present = [m for m in metrics if any(m in d["overall"] for d in results["retrievers"].values())]

    head = f"{'retriever':<12}" + "".join(f"{m:>9}" for m in present)
    print("\n" + head)
    print("-" * len(head))
    for name in RETRIEVER_ORDER:
        d = results["retrievers"].get(name)
        if not d:
            continue
        print(f"{name:<12}" + "".join(f"{d['overall'].get(m, 0):>9.3f}" for m in present))


def kind_table(results):
    kinds = [k for k in results["by_kind"] if k]
    if not kinds:
        return
    print("\n\nBy query kind (MRR)")
    head = f"{'retriever':<12}" + "".join(f"{k:>14}" for k in kinds)
    print(head)
    print("-" * len(head))
    for name in RETRIEVER_ORDER:
        if name not in results["retrievers"]:
            continue
        row = f"{name:<12}"
        for k in kinds:
            row += f"{results['by_kind'][k].get(name, {}).get('MRR', 0):>14.3f}"
        print(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--json", dest="json_out", default="")
    ap.add_argument("--queries", default=os.path.join("evaluation", "queries.json"))
    args = ap.parse_args()

    configure_logging()
    logging.getLogger().setLevel(logging.WARNING)

    concepts, relationships, _ = load_corpus()
    cases = load_cases(args.queries)

    cases, problems = resolve_cases(cases, concepts)
    if problems:
        print("\nGround-truth problems — these references match no concept:")
        for p in problems:
            print("  !", p)
        print()

    store, embedder = VectorStore(), Embedder()
    try:
        retrievers = build_retrievers(concepts, relationships, store, embedder)
        missing = [n for n in RETRIEVER_ORDER if retrievers.get(n) is None]
        if missing:
            print(f"Unavailable retrievers: {', '.join(missing)} (run run_index.py to enable semantic)")

        print(f"\nCorpus: {len(concepts)} concepts, {len(relationships)} relationships")
        print(f"Queries: {len(cases)}")

        results = evaluate(retrievers, cases, args.k)
        table(results)
        kind_table(results)

        if args.detail:
            for name in RETRIEVER_ORDER:
                d = results["retrievers"].get(name)
                if not d:
                    continue
                print(f"\n\n── {name} ── per query")
                for r in d["per_query"]:
                    mark = "ok " if r["MRR"] > 0 else "MISS"
                    print(f"  [{mark}] {r['id']} ({r['kind']:12}) MRR={r['MRR']:.3f}  {r['query'][:52]}")

        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n\nResults written to {args.json_out}")
        print()
    finally:
        store.close()


if __name__ == "__main__":
    main()

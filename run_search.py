"""
Query the retrieval engine from the CLI.

    python run_search.py "what does mini-batch SGD require?"
    python run_search.py --retriever graph "learning rate"
    python run_search.py --compare "how do I stop overshooting the minimum?"

--compare runs all four retrievers on the same query side by side, which is
the quickest way to see what graph-aware retrieval adds over keyword and
semantic search.
"""
import argparse
import logging
import sys

from config import settings
from logging_setup import configure_logging
from retrieval.embedder import Embedder
from retrieval.retrievers import build_retrievers, load_corpus
from retrieval.vector_store import VectorStore


def show(name, results, limit):
    print(f"\n── {name} " + "─" * (52 - len(name)))
    if not results:
        print("   (no results)")
        return
    for i, r in enumerate(results[:limit], 1):
        where = ""
        if r.filenames:
            pages = f" p{r.page_numbers[0]}" if r.page_numbers else ""
            where = f"  [{r.filenames[0][:28]}{pages}]"
        print(f"  {i}. {r.score:.4f}  {r.kind:7} {r.name[:44]}{where}")
        if r.text:
            print(f"      {r.text[:100]}")
        if r.extra.get("via"):
            print(f"      via: {r.extra['via']}")
        if r.extra.get("found_by"):
            print(f"      found by: {', '.join(r.extra['found_by'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("--retriever", choices=["keyword", "semantic", "graph", "hybrid"], default="hybrid")
    ap.add_argument("--compare", action="store_true", help="run all four retrievers")
    ap.add_argument("--top-k", type=int, default=settings.retrieval_top_k)
    args = ap.parse_args()

    configure_logging()
    logging.getLogger().setLevel(logging.WARNING)  # keep query output readable
    query = " ".join(args.query)

    concepts, relationships, _ = load_corpus()
    store, embedder = VectorStore(), Embedder()
    try:
        retrievers = build_retrievers(concepts, relationships, store, embedder)
        print(f"\nQuery: {query!r}   ({len(concepts)} concepts, {len(relationships)} relationships)")

        if args.compare:
            for name in ("keyword", "semantic", "graph", "hybrid"):
                r = retrievers[name]
                if r is None:
                    print(f"\n── {name} ── unavailable (run run_index.py)")
                    continue
                show(name, r.retrieve(query, args.top_k), args.top_k)
        else:
            r = retrievers[args.retriever]
            if r is None:
                print(f"{args.retriever} retriever unavailable — run run_index.py first")
                sys.exit(1)
            show(args.retriever, r.retrieve(query, args.top_k), args.top_k)
        print()
    finally:
        store.close()


if __name__ == "__main__":
    main()

"""
Ask the knowledge base a question.

    python run_ask.py "what does mini-batch SGD require?"
    python run_ask.py --json "what is a learning rate?"
"""
import argparse
import json
import logging

from logging_setup import configure_logging
from rag.models import QUERY_TYPES
from rag.pipeline import RAGPipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("--json", action="store_true", help="emit the full result as JSON")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    configure_logging()
    if not args.verbose:
        logging.getLogger().setLevel(logging.WARNING)
    query = " ".join(args.query)

    pipeline = RAGPipeline()
    try:
        result = pipeline.ask(query)
    finally:
        pipeline.close()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    print(f"\nQ: {result.query}")
    print(f"   type {result.query_type} ({QUERY_TYPES.get(result.query_type, '?')})"
          f" · retriever: {result.retriever_used} · model: {result.model_used}")
    if result.concepts_identified:
        print(f"   concepts: {', '.join(result.concepts_identified)}")

    print(f"\n{result.answer}\n")

    if not result.sufficient_evidence:
        print("!  The model reported the evidence as insufficient for this question.")
    if result.flags:
        print(f"!  flags: {', '.join(result.flags)}")

    used = [c for c in result.citations if c.index in result.used_citations]
    if used:
        print("\nSources:")
        for c in used:
            head = c.relationship or c.concept_name or "source text"
            print(f"  [{c.index}] {head}  —  {c.label()}")
            print(f"      {c.text[:110]}")
    print()


if __name__ == "__main__":
    main()

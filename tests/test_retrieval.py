"""
Tests for the retrieval engine.

Keyword, graph and hybrid are tested against fixtures with no model or vector
store involved — these assert ranking and fusion logic, not embedding quality.
Run with:  python tests/test_retrieval.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval.retrievers import (GraphRetriever, HybridRetriever, KeywordRetriever,
                                  RetrievalResult)

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))


CONCEPTS = [
    {"concept_id": "c1", "canonical_name": "Mini-Batch SGD", "definition": "Averages the gradient over a small batch.",
     "aliases": ["Mini-Batch SGD", "mini batch sgd"], "keywords": ["batch", "gradient"],
     "filenames": ["MiniBatch_SGD.pptx"], "page_numbers": [2], "chunk_ids": ["ch1"],
     "evidence": ["Average gradient over a small batch"], "occurrence_count": 3},
    {"concept_id": "c2", "canonical_name": "Batch Size", "definition": "Number of samples per update.",
     "aliases": ["Batch Size"], "keywords": ["batch"], "filenames": ["MiniBatch_SGD.pptx"],
     "page_numbers": [3], "chunk_ids": ["ch2"], "evidence": ["batch size b"], "occurrence_count": 2},
    {"concept_id": "c3", "canonical_name": "Learning Rate", "definition": "Controls the step size.",
     "aliases": ["Learning Rate"], "keywords": ["step"], "filenames": ["Batch_GD.pptx"],
     "page_numbers": [4], "chunk_ids": ["ch3"], "evidence": ["learning rate eta"], "occurrence_count": 5},
    {"concept_id": "c4", "canonical_name": "Hill Climbing", "definition": "A local search technique.",
     "aliases": ["Hill Climbing"], "keywords": ["search"], "filenames": ["Hill Climbing.pdf"],
     "page_numbers": [1], "chunk_ids": ["ch4"], "evidence": ["hill climbing search"], "occurrence_count": 4},
]

RELATIONSHIPS = [
    {"relationship_id": "r1", "source_concept_id": "c1", "source_name": "Mini-Batch SGD",
     "target_concept_id": "c2", "target_name": "Batch Size", "type": "requires",
     "evidence": [{"text": "Mini-batch SGD requires a batch size b", "chunk_id": "ch1", "scope": "chunk"}]},
    {"relationship_id": "r2", "source_concept_id": "c1", "source_name": "Mini-Batch SGD",
     "target_concept_id": "c3", "target_name": "Learning Rate", "type": "depends_on",
     "evidence": [{"text": "the update uses a learning rate", "chunk_id": "ch1", "scope": "cross_chunk"}]},
]


def test_keyword():
    print("\nKeyword retriever")
    r = KeywordRetriever(CONCEPTS)
    hits = r.retrieve("Mini-Batch SGD")
    check("exact name ranks first", hits and hits[0].id == "c1", f"got {hits[0].id if hits else None}")
    check("exact match scores 1.0", hits and hits[0].score == 1.0)
    check("case insensitive", KeywordRetriever(CONCEPTS).retrieve("mini-batch sgd")[0].id == "c1")
    check("token overlap finds partial", any(h.id == "c2" for h in r.retrieve("batch")))
    check("unrelated query returns nothing", r.retrieve("photosynthesis chlorophyll") == [])
    check("result carries provenance", hits[0].filenames == ["MiniBatch_SGD.pptx"] and hits[0].page_numbers == [2])


def test_graph():
    print("\nGraph retriever")
    seed = KeywordRetriever(CONCEPTS)
    g = GraphRetriever(CONCEPTS, RELATIONSHIPS, seed)
    hits = g.retrieve("Mini-Batch SGD")
    ids = [h.id for h in hits]
    check("seed concept present", "c1" in ids)
    check("expands to required neighbour", "c2" in ids, f"got {ids}")
    check("expands to depended-on neighbour", "c3" in ids, f"got {ids}")
    check("does NOT reach unrelated concept", "c4" not in ids, f"got {ids}")
    check("seed outranks neighbours", ids.index("c1") < ids.index("c2"))
    nb = next(h for h in hits if h.id == "c2")
    check("neighbour records the traversed edge", "requires" in nb.extra.get("via", ""), nb.extra.get("via"))
    check("neighbour carries relationship evidence", bool(nb.extra.get("relationship_evidence")))
    check("no seed -> no results", g.retrieve("photosynthesis chlorophyll") == [])


class StubRetriever:
    def __init__(self, name, ids):
        self.name = name
        self._ids = ids

    def retrieve(self, query, top_k=None):
        return [RetrievalResult(kind="concept", id=i, name=i, text="", score=1.0, retriever=self.name)
                for i in self._ids]


def test_hybrid():
    print("\nHybrid fusion")
    h = HybridRetriever(
        keyword=StubRetriever("keyword", ["c1", "c2"]),
        semantic=StubRetriever("semantic", ["c2", "c3"]),
        graph=StubRetriever("graph", ["c2", "c4"]),
    )
    hits = h.retrieve("q", top_k=10)
    ids = [x.id for x in hits]
    check("deduplicates across retrievers", len(ids) == len(set(ids)), f"got {ids}")
    check("all unique results returned", set(ids) == {"c1", "c2", "c3", "c4"}, f"got {ids}")
    check("item found by all three ranks first", ids[0] == "c2", f"got {ids}")
    c2 = next(x for x in hits if x.id == "c2")
    check("records which retrievers found it", c2.extra["found_by"] == ["graph", "keyword", "semantic"],
          str(c2.extra.get("found_by")))
    check("labelled as hybrid", all(x.retriever == "hybrid" for x in hits))

    print("\nHybrid degradation")
    only_kw = HybridRetriever(keyword=StubRetriever("keyword", ["c1"]), semantic=None, graph=None)
    check("works with semantic unavailable", [x.id for x in only_kw.retrieve("q")] == ["c1"])

    class Broken:
        name = "broken"
        def retrieve(self, q, top_k=None): raise RuntimeError("down")

    resilient = HybridRetriever(keyword=StubRetriever("keyword", ["c1"]), semantic=Broken(), graph=None)
    check("survives a failing retriever", [x.id for x in resilient.retrieve("q")] == ["c1"])


if __name__ == "__main__":
    for t in (test_keyword, test_graph, test_hybrid):
        t()
    failed = [r for r in results if not r[1]]
    print(f"\n{'=' * 54}\n{len(results) - len(failed)}/{len(results)} checks passed")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
    sys.exit(1 if failed else 0)

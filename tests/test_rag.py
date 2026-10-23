"""
Tests for the RAG pipeline's own guarantees.

The LLM is stubbed: these assert routing, evidence assembly and citation
validation — not answer quality. Run with:  python tests/test_rag.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.evidence import assemble, format_for_prompt
from rag.generator import AnswerGenerator
from rag.models import TYPE_A, TYPE_B, TYPE_C, Citation
from rag.understanding import QueryUnderstander
from retrieval.retrievers import RetrievalResult

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))


class StubLLM:
    def __init__(self, payload):
        self.payload = payload

    def call(self, prompt, system_instruction, schema):
        return json.dumps(self.payload), "stub-model"


class DeadLLM:
    def call(self, prompt, system_instruction, schema):
        return None


CONCEPTS_BY_ID = {
    "k1": {"concept_id": "k1", "canonical_name": "Mini-Batch SGD",
           "definition": "Averages the gradient over a small batch.",
           "evidence": ["Average gradient over a small batch of b samples", "b is the batch size"]},
    "k2": {"concept_id": "k2", "canonical_name": "Batch Size",
           "definition": "Number of samples per update.", "evidence": ["batch size b"]},
}

RELATIONSHIPS = [
    {"source_concept_id": "k1", "source_name": "Mini-Batch SGD",
     "target_concept_id": "k2", "target_name": "Batch Size", "type": "requires",
     "evidence": [{"text": "Mini-batch SGD requires a batch size b", "filename": "f.pptx",
                   "location_number": 3, "chunk_id": "ch1"}]},
    # endpoint k9 was never retrieved — must not be offered to the generator
    {"source_concept_id": "k1", "source_name": "Mini-Batch SGD",
     "target_concept_id": "k9", "target_name": "Unretrieved", "type": "produces",
     "evidence": [{"text": "should not appear", "filename": "f.pptx",
                   "location_number": 9, "chunk_id": "ch9"}]},
]


def _result(kind, id, name, text, files=("f.pptx",), pages=(2,)):
    return RetrievalResult(kind=kind, id=id, name=name, text=text, score=0.9,
                           retriever="stub", filenames=list(files),
                           page_numbers=list(pages), chunk_ids=["ch1"])


def test_understanding():
    print("\nQuery understanding")
    names = ["Mini-Batch SGD", "Batch Size", "Learning Rate"]

    u = QueryUnderstander(names, llm=StubLLM(
        {"query_type": "B", "concepts": ["Mini-Batch SGD", "Batch Size"], "reasoning": "r"}))
    out = u.understand("what does mini-batch SGD require?")
    check("classifies type B", out.query_type == TYPE_B, out.query_type)
    check("returns identified concepts", out.concepts == ["Mini-Batch SGD", "Batch Size"])

    # Model naming a concept that does not exist must not leak through.
    u2 = QueryUnderstander(names, llm=StubLLM(
        {"query_type": "A", "concepts": ["Backpropagation", "Batch Size"], "reasoning": "r"}))
    check("drops invented concept names", u2.understand("q").concepts == ["Batch Size"],
          str(u2.understand("q").concepts))

    u3 = QueryUnderstander(names, llm=StubLLM(
        {"query_type": "Z", "concepts": [], "reasoning": "r"}))
    check("invalid type falls back to heuristic", u3.understand("what is SGD?").query_type in (TYPE_A, TYPE_B, TYPE_C))

    u4 = QueryUnderstander(names, llm=DeadLLM())
    check("heuristic: relationship verb -> B", u4.understand("what does X require?").query_type == TYPE_B)
    check("heuristic: 'what is' -> A", u4.understand("what is a gradient?").query_type == TYPE_A)
    check("survives total LLM failure", u4.understand("q").query_type in (TYPE_A, TYPE_B, TYPE_C))


def test_evidence():
    print("\nEvidence assembly")
    res = [_result("concept", "k1", "Mini-Batch SGD", "Averages the gradient over a small batch."),
           _result("concept", "k2", "Batch Size", "Number of samples per update."),
           _result("chunk", "ch5", "f.pptx", "Raw slide text about batches.")]
    cits = assemble(res, CONCEPTS_BY_ID, RELATIONSHIPS)

    check("citations numbered from 1 without gaps",
          [c.index for c in cits] == list(range(1, len(cits) + 1)))
    kinds = {c.kind for c in cits}
    rel_idx = next(c.index for c in cits if c.kind == "relationship")
    span_idx = [c.index for c in cits if c.kind == "concept" and c.text.startswith("Average gradient")]
    check("relationship evidence ranks ahead of extra concept spans",
          not span_idx or rel_idx < span_idx[0], f"rel at {rel_idx}, span at {span_idx}")
    check("includes concept evidence", "concept" in kinds)
    check("includes relationship evidence", "relationship" in kinds, str(kinds))
    check("includes chunk evidence", "chunk" in kinds, str(kinds))

    texts = " ".join(c.text for c in cits)
    check("EXCLUDES edge to unretrieved concept", "should not appear" not in texts)
    rel = next(c for c in cits if c.kind == "relationship")
    check("relationship carries direction label", rel.relationship == "Mini-Batch SGD -requires-> Batch Size",
          rel.relationship)
    check("relationship carries page provenance", rel.page_number == 3 and rel.filename == "f.pptx")

    dupes = assemble([_result("concept", "k1", "Mini-Batch SGD", "same"),
                      _result("concept", "k1", "Mini-Batch SGD", "same")],
                     CONCEPTS_BY_ID, [])
    check("deduplicates repeated evidence", len({c.text for c in dupes}) == len(dupes))
    check("prompt format includes numbers", "[1]" in format_for_prompt(cits))


def test_generation():
    print("\nAnswer generation and citation validation")
    cits = [Citation(index=1, kind="concept", text="a", concept_name="A"),
            Citation(index=2, kind="concept", text="b", concept_name="B")]

    g = AnswerGenerator(llm=StubLLM({"answer": "Mini-batch SGD needs a batch size [1][2].",
                                     "used_citations": [1, 2], "sufficient_evidence": True, "flags": []}))
    data, model = g.generate("q", TYPE_B, cits)
    check("valid citations preserved", data["used_citations"] == [1, 2])
    check("no spurious flags", data["flags"] == [], str(data["flags"]))
    check("model recorded", model == "stub-model")

    # Cites [7] when only two citations exist — the dangerous case.
    g2 = AnswerGenerator(llm=StubLLM({"answer": "It requires something [7].",
                                      "used_citations": [7], "sufficient_evidence": True, "flags": []}))
    d2, _ = g2.generate("q", TYPE_B, cits)
    check("flags hallucinated citation", "hallucinated_citation" in d2["flags"], str(d2["flags"]))
    check("strips invalid citation number", 7 not in d2["used_citations"])

    g3 = AnswerGenerator(llm=StubLLM({"answer": "An answer with no citation at all.",
                                      "used_citations": [], "sufficient_evidence": True, "flags": []}))
    check("flags uncited answer", "uncited_answer" in g3.generate("q", TYPE_C, cits)[0]["flags"])

    # A refusal has nothing to cite — flagging it would be a false positive.
    g3b = AnswerGenerator(llm=StubLLM({"answer": "The evidence does not cover this.",
                                       "used_citations": [], "sufficient_evidence": False, "flags": []}))
    check("refusal NOT flagged as uncited",
          "uncited_answer" not in g3b.generate("q", TYPE_C, cits)[0]["flags"])

    d4, _ = AnswerGenerator(llm=StubLLM({})).generate("q", TYPE_A, [])
    check("no evidence -> refuses to answer", d4["sufficient_evidence"] is False)
    check("no evidence -> flagged", "no_evidence_retrieved" in d4["flags"])

    d5, _ = AnswerGenerator(llm=DeadLLM()).generate("q", TYPE_A, cits)
    check("provider failure -> not marked sufficient", d5["sufficient_evidence"] is False)
    check("provider failure -> flagged", "generation_failed" in d5["flags"])


if __name__ == "__main__":
    for t in (test_understanding, test_evidence, test_generation):
        t()
    failed = [r for r in results if not r[1]]
    print(f"\n{'=' * 54}\n{len(results) - len(failed)}/{len(results)} checks passed")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
    sys.exit(1 if failed else 0)

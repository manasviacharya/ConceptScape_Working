"""
Tests for concept normalization and evidence-grounded relationship linking.

The LLM is stubbed throughout: these assert the pipeline's own rules — merging,
evidence verification, deduplication — not the model's behaviour. Run with:

    python tests/test_relationships.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from normalization.normalizer import match_key, normalize
from relationships.common import merge_relationships, verify_evidence
from relationships.cross_chunk import CrossChunkLinker
from relationships.models import EvidenceRecord, Relationship

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, condition, detail=""):
    results.append((name, PASS if condition else FAIL, detail))
    print(f"  [{PASS if condition else FAIL}] {name}" + (f" — {detail}" if detail and not condition else ""))


class StubLLM:
    """Returns a canned relationship payload instead of calling a provider."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def call(self, prompt, system_instruction, schema):
        self.calls += 1
        return json.dumps(self.payload), "stub-model"


def _mention(name, chunk_id, concept_id, definition="d", evidence="e"):
    return {
        "concept_id": concept_id,
        "concept_name": name,
        "definition": definition,
        "evidence": evidence,
        "confidence": 0.9,
        "keywords": [],
        "model_used": "stub",
        "source_reference": {
            "resource_id": "doc_1", "filename": "f.pptx",
            "chunk_id": chunk_id, "slide_number": 1,
        },
    }


# ── Test A — concept variants merge into one canonical concept ────────────
def test_a_concept_variants():
    print("\nTest A — concept name variants merge")
    mentions = [
        _mention("Gradient Descent", "c1", "m1"),
        _mention("gradient descent", "c2", "m2"),
        _mention("Gradient Descent (GD)", "c3", "m3"),
    ]
    out = normalize(mentions)
    check("three variants -> one concept", len(out) == 1, f"got {len(out)}")
    if out:
        c = out[0]
        check("all mentions preserved", len(c.mention_ids) == 3, f"got {len(c.mention_ids)}")
        check("all chunk_ids preserved", set(c.chunk_ids) == {"c1", "c2", "c3"}, f"got {c.chunk_ids}")
        check("occurrence_count correct", c.occurrence_count == 3)
        check("aliases retained", len(c.aliases) == 3, f"got {c.aliases}")
    check("plural folding", match_key("Neural Networks") == match_key("Neural Network"))
    check("distinct concepts stay distinct", match_key("Gradient Descent") != match_key("Hill Climbing"))


# ── Test B — cross-chunk relationship with real supporting evidence ───────
def test_b_cross_chunk_supported():
    print("\nTest B — cross-chunk relationship IS created when evidence exists")
    chunks = {
        "c1": {"chunk_id": "c1", "text": "Gradient descent uses a learning rate to control update size.",
               "raw_page_text": "", "filename": "f.pptx", "location_number": 1},
        "c2": {"chunk_id": "c2", "text": "The learning rate determines how large each parameter update is.",
               "raw_page_text": "", "filename": "f.pptx", "location_number": 2},
    }
    concepts = [
        {"concept_id": "k1", "canonical_name": "Gradient Descent", "definition": "", "aliases": [],
         "evidence": ["Gradient descent uses a learning rate"], "chunk_ids": ["c1"]},
        {"concept_id": "k2", "canonical_name": "Learning Rate", "definition": "", "aliases": [],
         "evidence": ["The learning rate determines how large each parameter update is."], "chunk_ids": ["c2"]},
    ]
    linker = CrossChunkLinker(llm=StubLLM({"relationships": [{
        "source": "Gradient Descent", "target": "Learning Rate", "type": "requires",
        "evidence": "Gradient descent uses a learning rate to control update size.",
        "confidence": 0.9,
    }]}))
    rels, drops = linker.link_document(
        "doc_1", "f.pptx", concepts, chunks, [],
        {"gradient descent": "k1", "learning rate": "k2"},
        {"k1": "Gradient Descent", "k2": "Learning Rate"},
    )
    check("relationship created", len(rels) == 1, f"got {len(rels)}")
    if rels:
        r = rels[0]
        check("direction preserved", r.source_concept_id == "k1" and r.target_concept_id == "k2")
        check("type from vocabulary", r.type == "requires", f"got {r.type}")
        check("scope marked cross_chunk", r.evidence[0].scope == "cross_chunk")
        check("provenance: chunk recorded", r.evidence[0].chunk_id == "c1", f"got {r.evidence[0].chunk_id}")
        check("model_used recorded", r.evidence[0].model_used == "stub-model")


# ── Test C — no edge when the model invents unsupported evidence ──────────
def test_c_unsupported_rejected():
    print("\nTest C — relationship REJECTED when evidence is not in the source")
    chunks = {
        "c1": {"chunk_id": "c1", "text": "Gradient Descent is discussed here in general terms.",
               "raw_page_text": "", "filename": "f.pptx", "location_number": 1},
        "c2": {"chunk_id": "c2", "text": "Learning Rate is defined separately on this slide.",
               "raw_page_text": "", "filename": "f.pptx", "location_number": 2},
    }
    concepts = [
        {"concept_id": "k1", "canonical_name": "Gradient Descent", "definition": "", "aliases": [],
         "evidence": ["Gradient Descent is discussed here in general terms."], "chunk_ids": ["c1"]},
        {"concept_id": "k2", "canonical_name": "Learning Rate", "definition": "", "aliases": [],
         "evidence": ["Learning Rate is defined separately on this slide."], "chunk_ids": ["c2"]},
    ]
    # Plausible-sounding but absent from both chunks — exactly what grounding must catch.
    linker = CrossChunkLinker(llm=StubLLM({"relationships": [{
        "source": "Gradient Descent", "target": "Learning Rate", "type": "requires",
        "evidence": "Gradient descent requires a learning rate to converge properly.",
        "confidence": 0.95,
    }]}))
    rels, drops = linker.link_document(
        "doc_1", "f.pptx", concepts, chunks, [],
        {"gradient descent": "k1", "learning rate": "k2"},
        {"k1": "Gradient Descent", "k2": "Learning Rate"},
    )
    check("NO edge created", len(rels) == 0, f"got {len(rels)}")
    check("counted as unverifiable", drops.get("unverified") == 1, f"got {drops}")


def test_c2_unknown_endpoint():
    print("\nTest C2 — relationship REJECTED when an endpoint is not a known concept")
    chunks = {"c1": {"chunk_id": "c1", "text": "Gradient descent uses a learning rate to control update size.",
                     "raw_page_text": "", "filename": "f.pptx", "location_number": 1}}
    concepts = [
        {"concept_id": "k1", "canonical_name": "Gradient Descent", "definition": "", "aliases": [],
         "evidence": ["Gradient descent uses a learning rate to control update size."], "chunk_ids": ["c1"]},
        {"concept_id": "k2", "canonical_name": "Learning Rate", "definition": "", "aliases": [],
         "evidence": ["control update size"], "chunk_ids": ["c1"]},
    ]
    linker = CrossChunkLinker(llm=StubLLM({"relationships": [{
        "source": "Gradient Descent", "target": "Backpropagation",  # never extracted
        "type": "requires",
        "evidence": "Gradient descent uses a learning rate to control update size.",
        "confidence": 0.9,
    }]}))
    rels, drops = linker.link_document(
        "doc_1", "f.pptx", concepts, chunks, [],
        {"gradient descent": "k1", "learning rate": "k2"},
        {"k1": "Gradient Descent", "k2": "Learning Rate"},
    )
    check("NO edge to invented concept", len(rels) == 0, f"got {len(rels)}")
    check("counted as unknown endpoint", drops.get("unknown") == 1, f"got {drops}")


# ── Test D — duplicates collapse into one edge with multiple evidence ─────
def test_d_dedup():
    print("\nTest D — duplicate relationships merge into one edge")
    def rel(text, chunk_id, scope):
        return Relationship(
            relationship_id="rel_x", source_concept_id="k1", source_name="Gradient Descent",
            target_concept_id="k2", target_name="Learning Rate", type="requires",
            resource_id="doc_1",
            evidence=[EvidenceRecord(text=text, verified_against="text", chunk_id=chunk_id,
                                     filename="f.pptx", location_number=1, confidence=0.9,
                                     model_used="stub", scope=scope)],
        )
    merged = merge_relationships([
        rel("evidence from slide one here", "c1", "chunk"),
        rel("evidence from slide two here", "c2", "cross_chunk"),
        rel("evidence from slide one here", "c1", "chunk"),  # exact duplicate
    ])
    check("three inputs -> one edge", len(merged) == 1, f"got {len(merged)}")
    if merged:
        m = merged[0]
        check("two distinct evidence records kept", m.occurrence_count == 2, f"got {m.occurrence_count}")
        check("exact duplicate not re-added", len(m.evidence) == 2)
        check("both chunks in provenance", set(m.chunk_ids) == {"c1", "c2"}, f"got {m.chunk_ids}")
        check("different relationship types stay separate",
              len(merge_relationships([rel("evidence from slide one here", "c1", "chunk"),
                                       Relationship(relationship_id="rel_y", source_concept_id="k1",
                                                    source_name="a", target_concept_id="k2", target_name="b",
                                                    type="part_of", resource_id="doc_1", evidence=[])])) == 2)


def test_e_verify_evidence():
    print("\nTest E — evidence verification primitives")
    src = [("text", "The learning  rate CONTROLS the step size.")]
    check("whitespace/case insensitive", verify_evidence("the learning rate controls", src) == "text")
    check("absent span rejected", verify_evidence("gradient descent converges", src) is None)
    check("too-short span rejected", verify_evidence("the", src) is None)
    check("empty span rejected", verify_evidence("", src) is None)
    check("falls back to second source",
          verify_evidence("only in raw", [("text", "nothing"), ("raw_page_text", "only in raw page")]) == "raw_page_text")


if __name__ == "__main__":
    for t in (test_a_concept_variants, test_b_cross_chunk_supported, test_c_unsupported_rejected,
              test_c2_unknown_endpoint, test_d_dedup, test_e_verify_evidence):
        t()
    failed = [r for r in results if r[1] == FAIL]
    print(f"\n{'='*54}\n{len(results)-len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:")
        for name, _, detail in failed:
            print(f"  - {name} {detail}")
    sys.exit(1 if failed else 0)

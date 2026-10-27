"""
An answer must not display a citation it cannot support.

Flagging a hallucinated citation while leaving "[7]" in the prose still shows
the reader a sourced-looking claim and sends them hunting for evidence that was
never supplied. These tests pin the stricter behaviour: invalid markers are
removed from the text, valid ones survive untouched, and a grounded-looking
answer with no citations at all is called out.
"""

import pytest

from rag.generator import AnswerGenerator
from rag.models import Citation


@pytest.fixture()
def citations():
    return [
        Citation(index=1, kind="concept", text="SGD updates after each example",
                 concept_name="SGD", filename="deck.pptx", page_number=3,
                 location_type="slide"),
        Citation(index=2, kind="concept", text="Mini-batch uses small batches",
                 concept_name="Mini-Batch SGD", filename="notes.pdf", page_number=11,
                 location_type="page"),
    ]


@pytest.fixture()
def generator():
    return AnswerGenerator.__new__(AnswerGenerator)  # no provider needed for _validate


def test_invalid_citation_marker_is_removed_from_the_answer(generator, citations):
    data = {
        "answer": "SGD updates after each example [1]. It always converges fastest [7].",
        "used_citations": [1, 7],
        "sufficient_evidence": True,
        "flags": [],
    }
    out = generator._validate(data, citations)

    assert "[7]" not in out["answer"], "a citation pointing at nothing must not be shown"
    assert "[1]" in out["answer"], "valid citations must survive"
    assert "hallucinated_citation" in out["flags"]
    assert out["used_citations"] == [1]


def test_valid_citations_are_untouched(generator, citations):
    data = {
        "answer": "SGD updates per example [1]; mini-batch uses batches [2].",
        "used_citations": [1, 2],
        "sufficient_evidence": True,
        "flags": [],
    }
    out = generator._validate(data, citations)
    assert out["answer"] == data["answer"]
    assert out["used_citations"] == [1, 2]
    assert "hallucinated_citation" not in out["flags"]


def test_claimed_but_unsupplied_citation_is_dropped(generator, citations):
    data = {
        "answer": "SGD updates after each example [1].",
        "used_citations": [1, 9],
        "sufficient_evidence": True,
        "flags": [],
    }
    out = generator._validate(data, citations)
    assert out["used_citations"] == [1]
    assert "invalid_citation_removed" in out["flags"]


def test_grounded_answer_with_no_citations_is_flagged(generator, citations):
    data = {
        "answer": "Mini-batch SGD is generally the best optimizer to use.",
        "used_citations": [],
        "sufficient_evidence": True,
        "flags": [],
    }
    out = generator._validate(data, citations)
    assert "uncited_answer" in out["flags"]


def test_refusal_is_not_flagged_as_uncited(generator, citations):
    """Declining to answer legitimately has nothing to cite."""
    data = {
        "answer": "The material does not discuss quantum teleportation.",
        "used_citations": [],
        "sufficient_evidence": False,
        "flags": [],
    }
    out = generator._validate(data, citations)
    assert "uncited_answer" not in out["flags"]
    assert out["sufficient_evidence"] is False


def test_no_evidence_produces_a_refusal_not_an_answer(citations):
    generator = AnswerGenerator.__new__(AnswerGenerator)
    data, model = generator.generate("what is quantum teleportation?", "C", [])
    assert data["sufficient_evidence"] is False
    assert data["flags"] == ["no_evidence_retrieved"]
    assert data["used_citations"] == []
    assert model == ""


def test_relationship_vocabulary_is_explained_to_the_model():
    """The two zero-precision types need their schema meaning spelled out."""
    from config import settings
    from relationships.common import vocabulary_guidance

    guidance = vocabulary_guidance(settings.relationship_types)
    assert "part_of:" in guidance and "COMPONENT" in guidance
    assert "causes:" in guidance and "BRINGS ABOUT" in guidance
    # Each allowed type must be documented, or the model is guessing again.
    for relationship_type in settings.relationship_types:
        assert f"{relationship_type}:" in guidance


def test_grouped_citations_are_recognised(generator, citations):
    """Models write "[1,8]" as readily as "[1][8]"; both must validate."""
    data = {
        "answer": "Mini-batch SGD requires b samples [1,2] and a gradient [1, 2].",
        "used_citations": [],
        "sufficient_evidence": True,
        "flags": [],
    }
    out = generator._validate(data, citations)
    assert out["used_citations"] == [1, 2]
    assert "uncited_answer" not in out["flags"], "a cited answer must not be called uncited"


def test_invalid_member_of_a_group_is_dropped_but_valid_ones_kept(generator, citations):
    data = {
        "answer": "Requires b samples [1,99] and converges fast [42].",
        "used_citations": [],
        "sufficient_evidence": True,
        "flags": [],
    }
    out = generator._validate(data, citations)
    assert "[1]" in out["answer"]
    assert "99" not in out["answer"] and "42" not in out["answer"]
    assert out["used_citations"] == [1]
    assert "hallucinated_citation" in out["flags"]

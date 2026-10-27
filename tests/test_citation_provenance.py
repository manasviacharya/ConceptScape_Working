"""
A citation must point at the source its quote was actually read from.

A fused concept unions filenames and page numbers over every merged mention,
so the position of a span in `evidence` says nothing about which file it came
from. These tests pin the property that makes a citation auditable: the span,
the file and the page/slide travel together, and a position is never labelled
with a unit it does not have.
"""


from rag.evidence import assemble
from rag.models import Citation
from retrieval.retrievers import RetrievalResult


def _concept_result(concept_id="c1", name="Mini-Batch SGD"):
    """A concept fused from two sources — a deck and a PDF."""
    return RetrievalResult(
        kind="concept",
        id=concept_id,
        name=name,
        text="",
        score=0.9,
        retriever="hybrid",
        filenames=["Batch_GD.pptx", "Hill Climbing.pdf"],
        page_numbers=[3, 11],
        chunk_ids=["ppt_c000", "pdf_c007"],
    )


FUSED_CONCEPT = {
    "concept_id": "c1",
    "canonical_name": "Mini-Batch SGD",
    "definition": "An optimizer that updates parameters on small batches.",
    "definition_source": {
        "filename": "Hill Climbing.pdf",
        "location_type": "page",
        "location_number": 11,
        "chunk_id": "pdf_c007",
    },
    "filenames": ["Batch_GD.pptx", "Hill Climbing.pdf"],
    "page_numbers": [3, 11],
    "evidence": [
        "mini-batch SGD splits the training set into small batches",
        "each batch yields one parameter update",
    ],
    "evidence_records": [
        {
            "text": "mini-batch SGD splits the training set into small batches",
            "filename": "Batch_GD.pptx",
            "location_type": "slide",
            "location_number": 3,
            "chunk_id": "ppt_c000",
        },
        {
            "text": "each batch yields one parameter update",
            "filename": "Hill Climbing.pdf",
            "location_type": "page",
            "location_number": 11,
            "chunk_id": "pdf_c007",
        },
    ],
}


def _by_text(citations, needle):
    for c in citations:
        if needle in c.text:
            return c
    raise AssertionError(f"no citation containing {needle!r}")


def test_each_span_cites_its_own_source(monkeypatch):
    """The decisive case: two spans of one fused concept, two different files."""
    from config import settings

    monkeypatch.setattr(settings, "rag_evidence_per_concept", 2)

    citations = assemble([_concept_result()], {"c1": FUSED_CONCEPT}, [])

    slide_span = _by_text(citations, "splits the training set")
    assert slide_span.filename == "Batch_GD.pptx"
    assert slide_span.page_number == 3

    page_span = _by_text(citations, "each batch yields")
    assert page_span.filename == "Hill Climbing.pdf"
    assert page_span.page_number == 11


def test_definition_cites_the_mention_it_came_from():
    citations = assemble([_concept_result()], {"c1": FUSED_CONCEPT}, [])
    definition = _by_text(citations, "updates parameters on small batches")
    assert definition.filename == "Hill Climbing.pdf"
    assert definition.page_number == 11


def test_slide_is_not_labelled_as_a_page(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "rag_evidence_per_concept", 2)
    citations = assemble([_concept_result()], {"c1": FUSED_CONCEPT}, [])
    assert _by_text(citations, "splits the training set").label() == "Batch_GD.pptx slide 3"
    assert _by_text(citations, "each batch yields").label() == "Hill Climbing.pdf p11"


def test_timestamp_renders_as_a_time():
    citation = Citation(
        index=1, kind="chunk", text="gradient descent walks downhill",
        filename="gradient_descent.yt", page_number=135, location_type="timestamp",
    )
    assert citation.label() == "gradient_descent.yt @2:15"


def test_relationship_evidence_keeps_its_own_location():
    relationship = {
        "source_concept_id": "c1",
        "target_concept_id": "c2",
        "source_name": "Mini-Batch SGD",
        "target_name": "Learning Rate",
        "type": "requires",
        "evidence": [{
            "text": "mini-batch SGD requires a learning rate",
            "filename": "Stochastic Gradient Descent.pptx",
            "location_type": "slide",
            "location_number": 7,
            "chunk_id": "ppt_c112",
        }],
    }
    results = [_concept_result(), _concept_result("c2", "Learning Rate")]
    concepts = {"c1": FUSED_CONCEPT, "c2": {"concept_id": "c2", "definition": "Step size."}}

    citations = assemble(results, concepts, [relationship])
    edge = _by_text(citations, "requires a learning rate")
    assert edge.filename == "Stochastic Gradient Descent.pptx"
    assert edge.page_number == 7
    assert edge.label() == "Stochastic Gradient Descent.pptx slide 7"


def test_legacy_concepts_without_records_still_cite_something(monkeypatch):
    """Artifacts generated before evidence_records existed must not crash."""
    from config import settings

    monkeypatch.setattr(settings, "rag_evidence_per_concept", 2)
    legacy = {
        "concept_id": "c1",
        "definition": "An optimizer.",
        "evidence": ["mini-batch SGD splits the training set"],
    }
    citations = assemble([_concept_result()], {"c1": legacy}, [])
    span = _by_text(citations, "splits the training set")
    assert span.filename == "Batch_GD.pptx"  # first source — the old behaviour
    assert span.page_number == 3


def test_ambiguous_location_type_is_not_guessed():
    """A concept mixing pages and slides must not claim either unit."""
    result = _concept_result()
    result.extra = {"locations": [{"type": "slide"}, {"type": "page"}]}
    legacy = {"concept_id": "c1", "definition": "An optimizer.", "evidence": []}
    citations = assemble([result], {"c1": legacy}, [])
    assert citations[0].location_type == ""
    assert citations[0].label() == "Batch_GD.pptx p3"

"""Regression tests that missing stage inputs fail the pipeline visibly."""

import pytest


@pytest.mark.parametrize("module_name", [
    "run_preprocessing",
    "run_extraction",
    "run_normalization",
    "run_relationships",
    "run_build_graph",
    "run_index",
])
def test_missing_stage_input_raises(monkeypatch, tmp_path, module_name):
    module = __import__(module_name)
    from config import settings

    monkeypatch.setattr(settings, "output_dir", str(tmp_path / "output"))
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    with pytest.raises(FileNotFoundError):
        module.main()


def test_failed_extraction_does_not_advance_to_normalization(monkeypatch, tmp_path):
    import json
    import run_extraction
    from config import settings

    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    output_dir.mkdir()
    (output_dir / "preprocessed_chunks.json").write_text(json.dumps({
        "subject_id": "subject_001",
        "chunks": [{"chunk_id": "c1", "content_hash": "h1", "text": "source"}],
    }))
    monkeypatch.setattr(settings, "output_dir", str(output_dir))
    monkeypatch.setattr(settings, "data_dir", str(data_dir))

    class FailedExtractor:
        def process_chunks(self, _data):
            return {"subject_id": "subject_001", "concepts": [], "failed_chunks": ["c1"]}

    monkeypatch.setattr(run_extraction, "ConceptExtractor", FailedExtractor)
    with pytest.raises(RuntimeError, match="downstream stages were not run"):
        run_extraction.main()
    assert (data_dir / "extracted_concepts.json").is_file()


def test_explicit_skip_preserves_success_and_records_failure_reason(monkeypatch, tmp_path):
    from extraction.extractor import ConceptExtractor
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "extraction_skip_chunks", ["c2"])
    monkeypatch.setattr(settings, "extraction_min_chunk_chars", 0)

    extractor = object.__new__(ConceptExtractor)

    def fake_extract(_text):
        return ([{
            "concept_name": "Gradient",
            "definition": "Gradient is a direction.",
            "evidence": "Gradient is a direction.",
            "confidence": 0.9,
            "keywords": ["gradient"],
            "relationships": [],
        }], "test-provider")

    monkeypatch.setattr(extractor, "extract_from_chunk", fake_extract)
    result = extractor.process_chunks({
        "subject_id": "subject_001",
        "chunks": [
            {"chunk_id": "c1", "content_hash": "h1", "text": "Gradient is a direction.", "resource_id": "r1", "filename": "a.pptx"},
            {"chunk_id": "c2", "content_hash": "h2", "text": "Skipped provider input.", "resource_id": "r1", "filename": "a.pptx"},
            {"chunk_id": "c3", "content_hash": "h3", "text": "Gradient is a direction.", "resource_id": "r1", "filename": "a.pptx"},
        ],
    })

    assert len(result["concepts"]) == 2
    assert set(result["processed_chunks"]) == {"c1", "c3"}
    assert result["failed_chunks"] == []
    assert result["skipped_chunks"] == [{
        "chunk_id": "c2",
        "resource_id": "r1",
        "filename": "a.pptx",
        "source_type": "",
        "location_type": "",
        "location_number": 0,
        "content_hash": "h2",
        "reason": "explicitly skipped after provider failure",
    }]

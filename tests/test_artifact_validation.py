"""Regression tests for generated-artifact identity validation."""

from scripts.validate_artifacts import validate_artifact_data


def _data(mention_subject="subject_001", concept_subject="subject_001"):
    return {
        "manifest": {"documents": ["demo.pptx"]},
        "ingestion": {"subject_id": "subject_001"},
        "chunks": {"subject_id": "subject_001", "chunks": [{"chunk_id": "ch1"}]},
        "mentions": {
            "subject_id": mention_subject,
            "concepts": [],
            "processed_chunks": {"ch1": "hash1"},
            "failed_chunks": [],
            "skipped_chunks": [],
        },
        "concepts": {
            "subject_id": concept_subject,
            "concepts": [{"concept_id": "k1", "chunk_ids": ["ch1"]}],
        },
        "relationships": {"subject_id": "subject_001", "relationships": []},
        "graph": {"nodes": [{"concept_id": "k1"}]},
    }


def test_subject_id_mismatch_is_reported_without_repairing_data():
    data = _data(mention_subject=None)
    errors = validate_artifact_data(**data, available_documents={"demo.pptx"})
    assert "subject_id differs between extraction and normalization" in errors
    assert data["mentions"].get("subject_id") is None


def test_coherent_subject_id_chain_passes():
    data = _data()
    assert validate_artifact_data(**data, available_documents={"demo.pptx"}) == []


def test_explicit_skipped_chunk_is_accounted_for():
    data = _data()
    data["chunks"]["chunks"].append({"chunk_id": "ch2"})
    data["mentions"].update({
        "processed_chunks": {"ch1": "hash1"},
        "failed_chunks": [],
        "skipped_chunks": [{
            "chunk_id": "ch2",
            "filename": "demo.pptx",
            "content_hash": "hash2",
            "reason": "explicitly skipped after provider failure",
        }],
    })
    assert validate_artifact_data(**data, available_documents={"demo.pptx"}) == []


def test_malformed_skipped_chunk_is_rejected():
    data = _data()
    data["mentions"].update({
        "processed_chunks": {"ch1": "hash1"},
        "failed_chunks": [],
        "skipped_chunks": [{"chunk_id": "missing", "reason": "unknown"}],
    })
    errors = validate_artifact_data(**data, available_documents={"demo.pptx"})
    assert "extraction skipped_chunks references missing chunks" in errors
    assert "skipped chunk missing missing filename" in errors

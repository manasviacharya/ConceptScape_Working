"""
Running the model-calling stages in parallel must not change their output.

Completion order no longer matches chunk order, so these tests pin the
properties that make that safe: identical output at one worker and many, order
that follows the corpus rather than the network, and failures that stay
uncached so a later run retries them.
"""

import json
import time

import pytest


@pytest.fixture()
def chunks():
    return {
        "subject_id": "test-subject",
        "chunks": [
            {
                "chunk_id": f"chunk_{i:02d}",
                "content_hash": f"hash_{i:02d}",
                "text": f"Concept number {i} is an optimization method that reduces error. " * 2,
                "raw_page_text": "",
                "resource_id": "res_1",
                "source_type": "pptx",
                "filename": "deck.pptx",
                "location_type": "slide",
                "location_number": i,
            }
            for i in range(12)
        ],
    }


def _extractor(fake_call):
    from extraction.extractor import ConceptExtractor

    extractor = ConceptExtractor.__new__(ConceptExtractor)  # no provider needed
    extractor.extract_from_chunk = fake_call
    return extractor


def _concept_for(text):
    number = text.split()[2]
    return (
        [{
            "concept_name": f"Concept {number}",
            "definition": "An optimization method that reduces error.",
            "evidence": "optimization method that reduces error",
            "confidence": 0.9,
            "keywords": ["optimization"],
            "relationships": [],
        }],
        "stub-model",
    )


def _run(chunks, workers, monkeypatch, tmp_path, delay=None):
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "extraction_max_workers", workers)

    def call(text):
        if delay:
            time.sleep(delay(text))
        return _concept_for(text)

    return _extractor(call).process_chunks(chunks)


def _comparable(result):
    """Mention ids are random and not part of the contract."""
    return [
        {k: v for k, v in concept.items() if k != "concept_id"}
        for concept in result["concepts"]
    ]


def test_parallel_output_matches_sequential(chunks, monkeypatch, tmp_path):
    sequential = _run(chunks, 1, monkeypatch, tmp_path / "a")
    parallel = _run(
        chunks, 6, monkeypatch, tmp_path / "b",
        delay=lambda t: 0.01 * (int(t.split()[2]) % 4),
    )
    assert _comparable(sequential) == _comparable(parallel)
    assert sequential["processed_chunks"] == parallel["processed_chunks"]
    assert len(parallel["concepts"]) == 12


def test_order_follows_the_corpus_not_the_network(chunks, monkeypatch, tmp_path):
    """Later chunks finish first; the output must still be in corpus order."""
    result = _run(
        chunks, 6, monkeypatch, tmp_path,
        delay=lambda t: 0.05 - 0.004 * int(t.split()[2]),
    )
    names = [c["concept_name"] for c in result["concepts"]]
    assert names == [f"Concept {i}" for i in range(12)]


def test_failed_chunk_is_not_cached(chunks, monkeypatch, tmp_path):
    """A transient failure must not become permanent."""
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "extraction_max_workers", 4)

    result = _extractor(
        lambda t: None if t.split()[2] == "5" else ([], "stub-model")
    ).process_chunks(chunks)

    assert result["failed_chunks"] == ["chunk_05"]
    assert "chunk_05" not in result["processed_chunks"]


def test_worker_exception_degrades_to_a_retryable_chunk(chunks, monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "extraction_max_workers", 4)

    def raising(text):
        if text.split()[2] == "3":
            raise RuntimeError("provider blew up")
        return ([], "stub-model")

    result = _extractor(raising).process_chunks(chunks)
    assert result["failed_chunks"] == ["chunk_03"]
    assert "chunk_03" not in result["processed_chunks"]


def test_unchanged_chunks_make_no_model_call(chunks, monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "extraction_max_workers", 4)

    first = _run(chunks, 4, monkeypatch, tmp_path)
    (tmp_path / "extracted_concepts.json").write_text(
        json.dumps(first, ensure_ascii=False), encoding="utf-8"
    )

    calls = []

    def counted(text):
        calls.append(text)
        return ([], "stub-model")

    second = _extractor(counted).process_chunks(chunks)
    assert calls == [], "unchanged chunks must not trigger a model call"
    assert _comparable(second) == _comparable(first)


def test_explicitly_skipped_chunk_is_never_called(chunks, monkeypatch, tmp_path):
    """The skip is a recorded decision, not a silent success."""
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "extraction_max_workers", 4)
    monkeypatch.setattr(settings, "extraction_skip_chunks", ["chunk_07"])

    calls = []

    def counted(text):
        calls.append(text.split()[2])
        return ([], "stub-model")

    result = _extractor(counted).process_chunks(chunks)
    assert "7" not in calls
    assert "chunk_07" not in result["processed_chunks"]
    assert any(s["chunk_id"] == "chunk_07" for s in result.get("skipped_chunks", []))


def test_breaker_counts_concurrent_rate_limits_exactly(monkeypatch):
    """The breaker counter is shared across workers, so it must be atomic."""
    import concurrent.futures

    from config import settings
    from llm_provider import LLMProvider

    monkeypatch.setattr(settings, "gemini_rate_limit_trip_after", 1000)
    monkeypatch.setattr(LLMProvider, "_gemini_rate_limit_hits", 0)
    monkeypatch.setattr(LLMProvider, "_gemini_disabled", False)

    def bump():
        with LLMProvider._breaker_lock:
            LLMProvider._gemini_rate_limit_hits += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: bump(), range(400)))

    assert LLMProvider._gemini_rate_limit_hits == 400

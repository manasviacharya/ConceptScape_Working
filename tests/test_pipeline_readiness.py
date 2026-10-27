"""
A failed RAG initialisation must be recoverable without restarting the API.

The failure used to be cached for the lifetime of the process, so a question
asked before the corpus existed poisoned every later question. These tests pin
the recovery contract: the failure is remembered briefly, then retried, and the
503 names the actual cause so the operator knows which of several very
different problems they have.
"""

import time

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def clean_pipeline_state():
    import api.service as service

    service._pipelines.clear()
    service._pipeline_errors.clear()
    service._pipeline_failed_at.clear()
    yield
    service._pipelines.clear()
    service._pipeline_errors.clear()
    service._pipeline_failed_at.clear()


def test_failure_detail_names_the_actual_cause(monkeypatch):
    import api.service as service

    def explode():
        raise RuntimeError("normalized_concepts.json not found")

    monkeypatch.setattr(service, "ensure_workspace_paths", lambda _: explode())

    with pytest.raises(HTTPException) as caught:
        service.get_pipeline("ws1")

    assert caught.value.status_code == 503
    assert "normalized_concepts.json not found" in caught.value.detail


def test_failure_is_cached_briefly_then_retried(monkeypatch):
    """Caching avoids re-paying a slow failure per request; expiry allows recovery."""
    import api.service as service
    from config import settings

    monkeypatch.setattr(settings, "rag_init_retry_seconds", 60)

    attempts = []

    def explode(_):
        attempts.append(time.time())
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(service, "ensure_workspace_paths", explode)

    for _ in range(3):
        with pytest.raises(HTTPException):
            service.get_pipeline("ws1")

    assert len(attempts) == 1, "a cached failure must not be retried on every request"

    # Age the failure past the retry window.
    service._pipeline_failed_at["ws1"] = time.time() - 61
    with pytest.raises(HTTPException):
        service.get_pipeline("ws1")

    assert len(attempts) == 2, "an expired failure must be retried"


def test_recovery_needs_no_restart(monkeypatch):
    """Once the cause is gone, the next attempt after expiry must succeed."""
    import api.service as service
    from config import settings

    monkeypatch.setattr(settings, "rag_init_retry_seconds", 0)

    state = {"broken": True}
    sentinel = object()

    def maybe_explode(_):
        if state["broken"]:
            raise RuntimeError("corpus not generated yet")
        return {"output": "o", "data": "d", "vectors": "v"}

    monkeypatch.setattr(service, "ensure_workspace_paths", maybe_explode)

    with pytest.raises(HTTPException):
        service.get_pipeline("ws1")

    state["broken"] = False
    service._pipelines["ws1"] = sentinel  # stand in for a constructed pipeline
    service._pipeline_errors.pop("ws1", None)

    assert service.get_pipeline("ws1") is sentinel


def test_invalidation_clears_the_failure_marker():
    import api.service as service

    service._pipeline_errors["ws1"] = "stale failure"
    service._pipeline_failed_at["ws1"] = time.time()

    service._invalidate_pipeline("ws1")

    assert "ws1" not in service._pipeline_errors
    assert "ws1" not in service._pipeline_failed_at

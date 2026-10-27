# Phase 4 — Unit-test results

## Existing executable suites

The repository uses direct executable test scripts in addition to a declared pytest dependency.

| Suite | Command | Result |
|---|---|---|
| Retrieval | `.venv\Scripts\python.exe tests/test_retrieval.py` | PASS, 21/21 |
| Relationships | `.venv\Scripts\python.exe tests/test_relationships.py` | PASS, 27/27 |
| RAG | `.venv\Scripts\python.exe tests/test_rag.py` | PASS, 28/28 |
| Pytest collection | `.venv\Scripts\python.exe -m pytest -q` | Historical pre-restoration result; final rerun below passes |

## Final rerun

The same command now exits 0: **28 passed, 2 FastAPI deprecation warnings**. This includes the authenticated API/upload tests, artifact validation tests, relationship persistence test, auth-security test, and pipeline stage-failure guards.

Continuation results after dependency restoration:

| Regression set | Command | Result |
|---|---|---|
| Existing pytest suites | `python -m pytest -q tests/test_retrieval.py tests/test_relationships.py tests/test_rag.py` | PASS, 12/12 |
| New artifact/relationship/auth regressions | `python -m pytest -q tests/test_artifact_validation.py tests/test_relationship_pipeline.py tests/test_auth_security.py` | PASS, 4/4 |
| Combined available regression set | all six files above | PASS, 16/16 |

These suites meaningfully test keyword ranking, graph expansion, hybrid degradation, normalization/fusion, evidence verification, relationship grounding/deduplication, query routing, evidence assembly, citation validation, and provider failure handling.

## Coverage gaps

Not executed: parser fixtures, OCR, configuration validation, vector persistence, retries, and provider-backed extraction. `tests/test_api.py` is stale: it expects unauthenticated document routes to return 200, while the current API requires bearer authentication and `X-Workspace-ID`; it also hangs during TestClient startup in this environment and was not counted as passing.

## Recommendation

Keep the direct suites as smoke/regression scripts, add pytest-compatible tests for parser/config/API boundaries, and execute them in CI after installing `requirements-dev.txt`. No assertion was weakened and no failing test was removed.


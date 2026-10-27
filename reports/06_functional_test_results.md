# Phase 6 — API, UI and end-to-end functional tests

## Scenario matrix

| Scenario | Status | Evidence/limitation |
|---|---|---|
| valid PDF upload | BLOCKED | API/runtime unavailable |
| PPTX upload | NOT TESTED end-to-end | parser code exists; current artifacts contain PPT resources |
| image/scanned OCR | BLOCKED | PaddleOCR/runtime unavailable |
| corrupt/empty/oversized/unsupported upload | NOT TESTED | endpoint code has validators, API unavailable |
| equivalent concept fusion | PASS isolated / NOT TESTED workflow | normalization and fusion checks pass directly |
| related-but-distinct concepts remain distinct | PASS isolated | relationship suite checks distinct concepts |
| duplicate processing/idempotency | NOT TESTED | no runnable pipeline/API |
| exact terminology question | PASS isolated / BLOCKED live | RAG suite uses stub LLM and citation fixtures |
| paraphrased question | NOT TESTED live | no generated evaluation results in current checkout |
| relationship question | PASS isolated / BLOCKED live | routing and relationship evidence tested with stubs |
| absent-corpus question | PASS isolated | no-evidence refusal tested |
| citation/source inspection | PASS isolated / BLOCKED UI | citation validation tested; frontend unavailable |
| restart persistence | NOT TESTED | services unavailable |
| unavailable dependency behavior | PASS isolated | provider failure and retriever degradation tested |
| actual frontend upload/chat/graph | BLOCKED | npm install/build failed and API unavailable |

No end-to-end PASS is claimed. Browser automation was not run because the frontend could not be installed or started.

Continuation functional evidence:

- API health: PASS (HTTP 200).
- Auth registration/JWT/workspace creation: PASS with isolated audit database and temporary audit-only secret.
- Authenticated PNG upload and listing: PASS (1 saved, 0 rejected, 1 listed).
- Frontend TypeScript: PASS.
- Frontend production build: PASS outside sandbox after removing network-dependent Google font loading; warnings remain for `themeColor` metadata placement.
- Provider-backed relationship extraction: BLOCKED by DNS/network failure; no fake edge was accepted.

The legacy `tests/test_api.py` remains NOT PASS because its expectations predate authentication/workspace requirements and it does not form a valid current end-to-end test.

# Canonical regeneration follow-up

The current corpus was re-ingested successfully (10 resources, 0 ingestion failures) and re-chunked (49 chunks). Extraction reached the verified providers and wrote 120 mentions, but one chunk failed and caused exit 1. Normalization, relationship, graph, and indexing were intentionally not run over a partial extraction artifact.

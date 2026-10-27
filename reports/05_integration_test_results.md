# Phase 5 — Integration-test results

## Results

No real integration test could be completed in this environment. The implementation paths exist, but parser, FastAPI, database, Qdrant and provider dependencies are unavailable.

Continuation evidence: the real API was started with isolated SQLite/Qdrant storage. Health returned 200, registration issued a JWT and workspace, and an authenticated multipart PNG upload was persisted and returned by `/documents`. The controlled relationship script executed the real `RelationshipExtractor` and LLM provider boundary, but both Gemini and Groq failed on DNS/network access, so it returned zero edges and one failed chunk without caching it. The stub-boundary regression then verified one evidence-backed edge through canonical IDs into `InMemoryGraphStore` and its neighbor query.

Final pipeline evidence: isolated real ingestion exited 0 with 9 resources from the documented corpus (the YouTube source was unavailable), preprocessing exited 0 with 40 chunks, and extraction attempted all 40 chunks but recorded 40 provider failures. New stage guards prevent normalization, relationship extraction, graph build, or indexing from being reported as successful after that failure.

Canonical regeneration follow-up: ingestion now completed 10/10 resources and preprocessing produced 49 chunks. Real extraction produced 120 mentions from 48 successful chunks, but one chunk remained uncached after Gemini quota/high-demand responses and Groq TPM/network failures; downstream stages were correctly stopped.

| Integration path | Status | Reason |
|---|---|---|
| extraction → cleaning → chunking | BLOCKED | PyMuPDF/PPTX runtime unavailable for fresh ingestion |
| concept extraction → normalization | NOT TESTED | Requires current corpus/provider or fixtures with full schema |
| embedding → Qdrant | BLOCKED | model/runtime and indexed current corpus not verified |
| graph writes → graph queries | NOT TESTED | current artifact has zero relationships; live graph not configured |
| query → retrieval → evidence | PARTIAL | isolated RAG/retrieval direct suites pass |
| evidence → provider → response | BLOCKED | no provider credentials/network |
| upload API → processing status | BLOCKED | FastAPI/uvicorn unavailable |
| duplicate/retry/persistence | NOT TESTED | requires runnable API/storage environment |

## Blocking data-integrity finding

`python scripts/validate_artifacts.py` fails before integration execution because the extracted artifact has no `subject_id` while normalized data has one. This is consistent with stale generated artifacts versus current extraction code, but it must be resolved by a real regeneration and validation run.


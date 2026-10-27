# Phase 10 — Final audit report

## Overall readiness

**NOT READY for a reliable full demonstration or research evaluation from this checkout.** The full pytest suite passes, and real ingestion/preprocessing was exercised on the documented corpus in isolated output directories. That run produced 9 resources and 40 chunks, but all 40 extraction calls failed because Gemini and Groq were unreachable. The canonical artifact chain still fails validation, and no generated artifacts were hand-edited to manufacture a pass.

## Verified counts

| Area | Result |
|---|---|
| Direct executable regression checks | 76/76 PASS |
| Full repository pytest suite | 28/28 PASS; 2 FastAPI deprecation warnings |
| API/stage regression subset | 12/12 PASS |
| Python compileall | PASS |
| Artifact validation | FAIL: `subject_id` mismatch |
| Pytest | PASS: 28/28 |
| Targeted Ruff | FAIL: 108 findings in existing pipeline scripts/tests |
| API startup/health | PASS in isolated loopback run |
| Authenticated API registration/upload | PASS in isolated loopback run |
| Frontend build/typecheck | PASS; build warnings remain |
| Canonical generated resources | 3 PPT |
| Canonical chunks/mentions/concepts/relationships | 53 / 93 / 80 / 0 |
| Isolated real ingestion/preprocessing | 9 resources / 40 chunks; one YouTube source unavailable |
| Isolated real extraction | 0 concepts / 0 mentions / 40 failed chunks; provider/network blocked |
| Retrieval/ablation result files | NOT PRESENT |
| AI/ML fresh metrics | Retrieval script computed keyword/graph/hybrid metrics on stale 80-concept/0-edge data; no complete evaluation claim |
| Live Qdrant | PASS only for embedded local API smoke mode; configured remote Qdrant unreachable |
| Live Neo4j | NOT TESTED |
| Live Gemini/Groq relationship extraction | BLOCKED by DNS/network |

## Implemented and verified

- Evidence verification and provenance-aware concept processing are implemented.
- Lexical normalization, fusion guards, relationship validation/deduplication, retriever compatibility, evidence assembly and citation validation are covered by direct tests.
- The repository includes API routes, workspace paths, pipeline status, upload validation, graph queries, quality reports and a frontend client; health/auth/upload and frontend build/typecheck were runtime-verified in an isolated environment.

## Partial or missing

- Current generated artifacts are stale/incomplete relative to the documented full corpus; isolated regeneration cannot advance beyond provider-backed extraction.
- The embedding default conflicts with the frozen BGE-M3 requirement. The current MiniLM setting was not silently changed; BGE-M3 versus MiniLM remains an explicit decision and verification task.
- Full API/UI browser E2E, provider-backed corpus regeneration, Neo4j persistence, performance and complete AI/ML evaluation remain blocked or untested.
- Historical benchmark values in `CONCEPTSCAPE_PAPER_CONTEXT.md` must not be presented as this audit’s fresh results.

## Exact reproduction commands

```powershell
python -m compileall -q api auth evaluation extraction graph ingestion normalization preprocessing rag relationships retrieval storage quality
.venv\Scripts\python.exe tests/test_retrieval.py
.venv\Scripts\python.exe tests/test_relationships.py
.venv\Scripts\python.exe tests/test_rag.py
.venv\Scripts\python.exe scripts/validate_artifacts.py
.venv\Scripts\python.exe -m pytest -q
python run_api.py
cd frontend; npm ci; npm run build; npx tsc --noEmit
$env:CONCEPTSCAPE_DOCUMENTS_DIR='documents'; $env:CONCEPTSCAPE_OUTPUT_DIR='audit_pipeline_output'; $env:CONCEPTSCAPE_DATA_DIR='audit_pipeline_data'
.venv\Scripts\python.exe run_ingestion.py              # exit 0, 9 resources
.venv\Scripts\python.exe run_preprocessing.py           # exit 0, 40 chunks
.venv\Scripts\python.exe run_extraction.py              # provider failures; 40 failed chunks
.venv\Scripts\python.exe run_evaluate.py                # exit 0, stale retrieval metrics only
.venv\Scripts\python.exe run_ablation.py                # exit 1, Windows cp1252 UnicodeEncodeError
```

## Prioritized remaining actions

1. Regenerate the canonical corpus through extraction → indexing with provider/network access, then make `scripts/validate_artifacts.py` pass.
2. Decide whether BGE-M3 remains mandatory; align `config.py`, documentation, Qdrant metadata and evaluation metadata explicitly.
3. Run browser E2E, Neo4j persistence/restart/failure-mode tests and fresh AI/ML evaluation after valid artifacts exist.
4. Address the targeted Ruff findings or explicitly adjust the configured Ruff policy.

## Latest canonical regeneration

The canonical run advanced through ingestion and preprocessing (10 resources, 49 chunks) and partially through real extraction (120 mentions, 1 failed chunk). Downstream stages were stopped by the stage guard. Artifact validation remains failing with stale downstream provenance/subject-ID errors; graph and vector outputs were not rebuilt for this run.

## Partial pipeline completion

After explicit approval, one provider-failed chunk (`ppt_3ba4e1df_slide_3_c000`) was recorded as skipped rather than treated as successful. The partial pipeline then completed normalization, real relationship extraction, isolated graph export, and isolated MiniLM/Qdrant indexing. Validation passed: 10 resources, 49 chunks, 120 mentions, 74 concepts, 81 relationships, 74 graph nodes, and 81 graph edges. Retrieval smoke passed across keyword, semantic, graph, and hybrid retrievers. The project remains unsuitable for full-corpus research claims because one slide's concepts/relationships are absent, Neo4j persistence was not verified, and remote Qdrant was replaced by an isolated local collection for this rebuild.


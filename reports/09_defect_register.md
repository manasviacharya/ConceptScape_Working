# Phase 9 — Defect register

| ID | Severity | Defect | Evidence | Fix status |
|---|---|---|---|---|
| D-001 | P1 | Current generated artifact chain is invalid because extraction and normalization disagree on `subject_id` | `python scripts/validate_artifacts.py` fails with `subject_id differs between extraction and normalization` | OPEN; safe fix is regeneration with current code, blocked by missing runtime/provider |
| D-002 | P1 | Declared application cannot start in the original dependency-free environment | Dependency restoration was required; after installing `requirements-dev.txt`, isolated uvicorn startup and health/auth/upload smoke passed | RESOLVED in this environment; clean environments still require dependency installation |
| D-003 | P2 | Current default embedding model conflicts with the frozen project decision and historical verified run | `config.py` selects MiniLM; skill/context specify BGE-M3 | OPEN; requires explicit product/research decision before changing user work |
| D-004 | P2 | Current artifact set does not represent the documented full corpus and has zero relationships | canonical counts 3 PPT / 53 chunks / 93 mentions / 80 concepts / 0 relationships; isolated real extraction produced 40 failed chunks | OPEN; provider/network access is required for regeneration, not hand-editing |
| D-005 | P2 | Quality lint and complete provider-backed verification remain incomplete | targeted Ruff reports 108 findings; provider calls and remote Qdrant fail DNS/network | OPEN; functional pytest/build/compile checks pass |
| D-006 | P1 | Authentication registration failed with installed bcrypt 5.x and Passlib 1.7.4 | live API returned 500; server trace showed Passlib bcrypt backend probe failure | FIXED; direct bcrypt hash/check plus regression test, live registration now passes |
| D-007 | P2 | Frontend production build required DNS access to Google Fonts | `next build` failed on `fonts.googleapis.com` before code compilation | FIXED; removed `next/font/google` runtime build dependency; build now passes |
| D-008 | P2 | Legacy API tests asserted pre-authentication behavior and hung through TestClient | tests were rewritten for bearer/workspace, upload validation, workspace isolation and direct service behavior; live smoke verified routes | FIXED; full pytest passes |
| D-009 | P1 | Pipeline stages previously returned success after missing inputs or failed extraction | isolated run could write empty downstream artifacts after 40 provider failures | FIXED; stage guards now raise and regression tests pass |

Generated artifacts were not edited to manufacture a pass. Source fixes include direct bcrypt compatibility, offline-safe frontend font loading, API-test contract migration, and pipeline stage guards. Artifact regeneration remains blocked by provider/network constraints.

## Regeneration update

The subject-ID producer path is now evidenced as correct through ingestion, preprocessing, and extraction (`subject_001`). The remaining validator mismatch is stale downstream data because extraction is incomplete; it is not being repaired by hand. The current blocker is provider quota/rate limiting plus restricted retry network access on one extraction chunk.

## Partial-processing update

| D-010 | P2 | One extraction chunk lacks concepts because provider quota/network failure required an approved skip | `ppt_3ba4e1df_slide_3_c000` is recorded in `skipped_chunks`; 48 chunks processed, 1 skipped | MITIGATED by explicit partial-processing manifest; retry remains possible |
| D-011 | P2 | Configured Neo4j backend was unreachable during graph rebuild | DNS failure for configured Neo4j endpoint; isolated NetworkX/memory export rebuilt instead | OPEN for remote persistence verification |
| D-012 | P2 | Configured remote Qdrant was not used during rebuild | Remote endpoint unavailable; isolated local Qdrant collections rebuilt with 384-dimension MiniLM vectors | OPEN for remote collection verification |


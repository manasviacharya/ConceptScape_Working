# Phase 3 — Build and startup verification

## Executed checks

| Command | Result | Evidence |
|---|---|---|
| `python --version` | PASS | Python 3.11.9 |
| `python -m compileall -q api auth evaluation extraction graph ingestion normalization preprocessing rag relationships retrieval storage quality` | PASS | Exit 0 |
| `.venv\Scripts\python.exe -m pytest -q` | PARTIAL | dependency restored; selected regression set passes, legacy API file hangs on its first stale test |
| `.venv\Scripts\python.exe -m ruff ...` | FAIL | dependency restored; 685 existing style findings reported |
| `python run_api.py --help` | PASS/NOT APPLICABLE | service imports now succeed; the script starts uvicorn rather than exposing CLI help |
| core parser imports | PASS | PyMuPDF, python-pptx and PaddleOCR imports succeed |

## Final rerun

After dependency restoration, `\.venv\Scripts\python.exe -m pytest -q` exited 0 with 28 passed and 2 FastAPI deprecation warnings. `compileall` exited 0. Frontend `npm.cmd run build` and `npx.cmd tsc --noEmit` both exited 0. Targeted Ruff exited 1 with 108 findings in the existing pipeline scripts/tests. The canonical validator exited 1 on the real subject-id mismatch.
| service imports | PASS | FastAPI/uvicorn imports succeed |
| `npm.cmd ci` in `frontend` | PASS | 93 packages installed from `package-lock.json` |
| `npm run build` | PASS with warnings | production build succeeds outside sandbox; Next warns about `metadata.themeColor` placement |
| `npx tsc --noEmit` | PASS | exit 0 |
| `python scripts/validate_artifacts.py` | FAIL | extraction/normalization `subject_id` mismatch |

An attempted `.venv` install of `pytest ruff` was blocked by unavailable DNS access to `pypi.org`; no dependencies were changed successfully.

## Startup status

The API was started on isolated loopback port 8011 with temporary audit-only JWT configuration and embedded Qdrant. `/health` returned HTTP 200 with database, storage and Qdrant healthy. Docker/Compose startup was not attempted because it requires external service images. Live Neo4j was not configured. Gemini/Groq relationship extraction was attempted but blocked by DNS/network access.

## Findings

- Python syntax/bytecode compilation is healthy.
- The declared CI workflow is now executable for dependency installation and frontend build, but fails the current Ruff gate and the legacy API test file remains incompatible with the authenticated API.
- The generated artifact chain is currently invalid; this prevents a trustworthy pipeline/search smoke test even if dependencies become available until the corpus is regenerated.


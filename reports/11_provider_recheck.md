# Provider recheck — 2026-10-27

## Configuration

- Settings keys: `CONCEPTSCAPE_GEMINI_API_KEY`, `CONCEPTSCAPE_GROQ_API_KEY`.
- Adapter-only fallback names also supported by `llm_provider.py`: `GEMINI_API_KEY`, `GROQ_API_KEY`. They were not needed; the prefixed settings keys were present.
- Gemini model: `gemini-3.6-flash`.
- Groq model: `openai/gpt-oss-120b`.
- Endpoint overrides: none. The SDKs use their managed defaults; the Groq SDK resolved to `https://api.groq.com`.
- Order: Gemini primary → Groq fallback → graceful failure.
- Embedding model remains the approved `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`.

Only boolean key-presence checks were printed. No key, header, request object, or environment dump was logged.

## Live results

| Provider | Result | Reached provider | HTTP status | Diagnostic |
|---|---|---:|---:|---|
| Gemini | PASS | Yes | 200 | Minimal `generate_content` request returned a real two-character response; no authentication, quota, model, or network error. |
| Groq | PASS via adapter | Yes | 400 observed on constrained probe; successful adapter status not exposed by SDK wrapper | The first tiny direct request reached Groq but returned empty content. An adapter-compatible JSON probe reached Groq and returned HTTP 400 because the artificially small 64-token budget ended before valid JSON. The actual adapter call succeeded with a real JSON response. This is a request-budget diagnostic, not an authentication or network failure. |

## Adapter and fallback verification

The real `LLMProvider.call(...)` was exercised with both configured providers:

- Normal routing returned `model_used=gemini-3.6-flash` and a non-empty response.
- Gemini was disabled only for the probe to force the configured fallback; the real Groq adapter call returned `model_used=openai/gpt-oss-120b` and a non-empty response.

No corpus regeneration was performed.

## Regression checks

```text
.venv\Scripts\python.exe -m pytest -q tests/test_api.py tests/test_pipeline_stage_failures.py tests/test_relationship_pipeline.py tests/test_auth_security.py tests/test_artifact_validation.py
16 passed, 2 warnings, exit 0
```

Targeted Ruff remains non-green with 17 existing findings in the inspected provider/config/test files; no unrelated cleanup was made.

## Recommended next action

Provider credentials and both configured provider paths are now working. Proceed with a controlled, isolated corpus regeneration and retain the existing canonical artifacts until extraction, normalization, relationship extraction, indexing, and artifact validation all complete successfully.

# Canonical corpus regeneration — blocked at extraction

## Source and commands

Authoritative corpus: `demo_corpus.json` with 10 files under `documents/`. Supported order is the commands in `run_pipeline.ps1`:

```powershell
.venv\Scripts\python.exe run_ingestion.py
.venv\Scripts\python.exe run_preprocessing.py
.venv\Scripts\python.exe run_extraction.py
.venv\Scripts\python.exe run_normalization.py
.venv\Scripts\python.exe run_relationships.py
.venv\Scripts\python.exe run_build_graph.py
.venv\Scripts\python.exe run_index.py
.venv\Scripts\python.exe scripts\validate_artifacts.py
```

Existing canonical counts were 3 resources, 53 chunks, 93 concepts, 80 normalized concepts, and 0 relationships. Existing graph/vector data was not deleted or manually edited.

## Actual run

| Stage | Command/result | Output evidence |
|---|---|---|
| Ingestion | `run_ingestion.py`, exit 0 | 10/10 resources, 0 failures; 4 PPTs, 4 images, 1 PDF, 1 YouTube source |
| Preprocessing | `run_preprocessing.py`, exit 0 | 49 chunks; `subject_id=subject_001` |
| Extraction, first run | `run_extraction.py`, exit 1 | 120 concept mentions from 48 successful chunks; 1 uncached failed chunk; `subject_id=subject_001` |
| Extraction retry | `run_extraction.py`, exit 1 | Same one chunk failed under restricted execution: Gemini DNS failure and Groq connection failure |
| Normalization onward | Not run | Correctly stopped because extraction still has a failed chunk |

The first live extraction run reached both providers. Gemini returned successful responses, then returned 503 high-demand and 429 quota responses; Groq successfully handled fallback calls but eventually returned TPM 429s. The final uncached chunk could not be retried in the restricted process because provider DNS/network access was unavailable. A subsequent elevated retry request was not approved.

## Identity and validator evidence

The regenerated ingestion, preprocessing, and extraction artifacts all carry `subject_id=subject_001`. The earlier mismatch was caused by stale downstream artifacts: `data/normalized_concepts.json` still has an empty subject ID and `data/relationships.json` is stale. The extraction producer already propagates the subject ID; no schema weakening or hand-edit was performed.

`scripts/validate_artifacts.py` was run and exited 1. It reports the stale normalization subject mismatch plus provenance references from the old normalized artifact to chunks no longer present in the regenerated preprocessing output. This failure remains visible.

## Stop condition

Normalization, relationship extraction, graph persistence, and MiniLM/Qdrant indexing were intentionally not run. Their existing outputs must not be treated as representing this regenerated corpus. Zero relationships cannot yet be evaluated because relationship extraction has not run on the complete regenerated concept set.

No source documents, credentials, or embedding configuration were changed. Existing remote Qdrant and Neo4j data were not cleared or modified; generated local graph/vector artifacts were rebuilt as documented below.

## Approved partial continuation

The team-approved explicit skip was applied with:

```powershell
$env:CONCEPTSCAPE_EXTRACTION_SKIP_CHUNKS='["ppt_3ba4e1df_slide_3_c000"]'
.venv\Scripts\python.exe run_extraction.py                 # exit 0
.venv\Scripts\python.exe run_normalization.py              # exit 0
.venv\Scripts\python.exe run_relationships.py              # exit 0
$env:CONCEPTSCAPE_NEO4J_URI=''; $env:CONCEPTSCAPE_GRAPH_ALLOW_MEMORY_FALLBACK='true'; .venv\Scripts\python.exe run_build_graph.py  # exit 0
$env:CONCEPTSCAPE_QDRANT_URL=''; $env:CONCEPTSCAPE_QDRANT_PATH='partial_qdrant_data'; $env:CONCEPTSCAPE_QDRANT_ALLOW_LOCAL_FALLBACK='true'; .venv\Scripts\python.exe run_index.py # exit 0
.venv\Scripts\python.exe scripts/validate_artifacts.py # exit 0
```

Final partial-corpus counts: **10 resources, 49 chunks, 120 concept mentions, 74 canonical concepts, 81 validated relationships, 74 graph nodes, 81 graph edges**. The extraction artifact records 48 processed chunks and one skipped chunk with source filename, resource ID, content hash, and the provider-failure reason. The skipped slide may have missing concepts and relationships; none were fabricated.

Graph construction used an isolated in-memory NetworkX fallback because configured Neo4j DNS was unavailable and the configured fallback was disabled. Remote Neo4j data was not cleared or modified. Indexing used isolated local Qdrant at `partial_qdrant_data`, preserving existing configured remote collections. Both collections contain 384-dimensional MiniLM vectors: 74 concept points and 49 chunk points.

Real retrieval smoke test, UTF-8 console:

```text
$env:CONCEPTSCAPE_QDRANT_URL=''; $env:CONCEPTSCAPE_QDRANT_PATH='partial_qdrant_data'; .venv\Scripts\python.exe run_search.py --compare --top-k 3 "what does mini-batch SGD require?"  # exit 0
```

Keyword, semantic, graph, and hybrid retrievers all returned grounded results; the top hybrid result was `Mini-Batch SGD` with provenance to `Gradient_Descent_Variants.pptx`, page/slide 2. The first attempt exposed a cp1252 console rendering error (exit 1), fixed operationally by UTF-8 console configuration; no retrieval code change was needed.

Final validation and regression: `scripts/validate_artifacts.py` exit 0; `.venv\Scripts\python.exe -m pytest -q` exit 0 with **31 passed, 2 warnings**. This is a validated partial pipeline, not full-corpus extraction or research readiness.

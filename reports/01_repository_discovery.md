# Phase 1 — Repository discovery

## Scope and evidence

Audit date: 2026-10-27 (Asia/Calcutta). The repository was inspected without resetting or overwriting the existing working tree. `git status --short --branch` reported `main...origin/main` with user modifications in API, configuration, pipeline, retrieval, frontend, deployment and quality files, plus untracked `quality/report.py`.

## Architecture map

```text
PDF/PPTX/image/YouTube
  -> ingestion dispatcher
  -> PyMuPDF / python-pptx / PaddleOCR / transcript parser
  -> preprocessing cleaner + sentence splitter + chunker
  -> extraction ConceptExtractor + LLMProvider + evidence verification
  -> normalization lexical normalizer + semantic_fusion guards
  -> relationships chunk and cross-chunk extractors
  -> graph NetworkX-compatible abstraction / Neo4j adapter
  -> retrieval keyword + semantic + graph + hybrid
  -> rag understanding + evidence assembly + grounded generator
  -> FastAPI /ask, /documents, /pipeline and frontend Next.js/React Flow
```

Important entry points: `run_ingestion.py`, `run_preprocessing.py`, `run_extraction.py`, `run_normalization.py`, `run_relationships.py`, `run_build_graph.py`, `run_index.py`, `run_ask.py`, `api/service.py`, and `frontend/app/*`.

## Stage ownership

| Stage | Main implementation | Storage/output |
|---|---|---|
| Ingestion | `ingestion/dispatcher.py`, `pdf_parser.py`, `ppt_parser.py`, `image_parser.py`, `ocr_engine.py` | `output/ingestion_result.json` |
| Preprocessing | `preprocessing/cleaner.py`, `splitter.py`, `chunker.py` | `output/preprocessed_chunks.json` |
| Concepts | `extraction/extractor.py`, `llm_provider.py` | `data/extracted_concepts.json` |
| Normalization/fusion | `normalization/normalizer.py`, `semantic_fusion.py` | `data/normalized_concepts*.json` |
| Relationships | `relationships/extractor.py`, `cross_chunk.py`, `common.py` | `data/relationships.json` |
| Graph | `graph/graph_store.py`, `memory_store.py`, `neo4j_store.py` | `data/graph_export.json` |
| Vectors | `retrieval/embedder.py`, `vector_store.py`, `run_index.py` | Qdrant/local path |
| Retrieval | `retrieval/retrievers.py` | compatible `RetrievalResult` |
| RAG | `rag/understanding.py`, `evidence.py`, `generator.py`, `pipeline.py` | API answer/citations |
| Product API | `api/service.py`, `api/pipeline_runner.py`, `storage/*`, `auth/*` | SQLite/PostgreSQL/workspace files |
| Frontend | `frontend/app`, `frontend/lib/api.ts`, React Flow components | Next.js UI |

## Key observations

- The current code includes a substantially expanded authenticated workspace/product API and learning/quality routes.
- The project context document describes a previous verified corpus and deliberately cut product scope; it conflicts with current architecture documentation and current route inventory. The requirement audit records both rather than assuming either is authoritative.
- Provenance fields are present in concept and relationship models, and evidence verification exists in extraction and relationship code.
- The frozen project skill requires BGE-M3, but current `config.py` defaults to `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`; this is a documented architecture/requirement mismatch.


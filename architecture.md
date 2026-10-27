# ConceptScape Architecture

ConceptScape converts educational documents into an evidence-grounded concept
knowledge graph and answers questions with citations back to source locations.
The application supports authenticated users, workspace isolation, persistent
documents and chat sessions, SQLite for local development, and PostgreSQL for
production. Pipeline jobs run in background threads with persisted status;
deployment-specific workers can replace the runner without changing the API.

## Current pipeline

```text
PDF/PPTX/image/YouTube URL file
        ↓
Native extraction or PaddleOCR
        ↓
Cleaning, sentence splitting, chunking
        ↓
Grounded concept extraction
        ↓
Lexical normalization + deterministic semantic fusion
        ↓
Evidence-verified relationship extraction
        ↓
Graph store export
        ↓
Keyword + semantic + graph-aware + hybrid retrieval
        ↓
Evidence assembly and citation validation
        ↓
Grounded RAG answer
```

## Components

### Ingestion

`ingestion/` contains parsers for PDF, PPT/PPTX, images, and `.yt`/`.youtube`
files. PDF pages use PyMuPDF native text when reliable and PaddleOCR only as a
fallback. Images and scanned PDF pages use PaddleOCR. OCR regions retain text,
confidence, and bounding boxes. YouTube files contain a URL; captions are
segmented into timestamped chunks.

### Preprocessing

`preprocessing/` normalizes Unicode, removes common headers/page numbers,
handles OCR line joining, splits sentences, and creates overlapping chunks.
Each processed chunk retains its raw page text for evidence verification.

### Extraction and normalization

`extraction/` calls the shared `LLMProvider` using Gemini first and Groq as a
fallback. Concepts must include source evidence, provenance, confidence, and
model metadata. `normalization/` performs case/plural/abbreviation handling,
lexical merging, and deterministic embedding-assisted fusion with rule guards.

### Relationships and graph

`relationships/` performs chunk-level and per-document cross-chunk extraction.
Only controlled relationship types with source-supported evidence are retained.
`graph/` exposes a storage abstraction with Neo4j as the remote implementation
and an in-memory fallback. Graph nodes and edges retain evidence and provenance.

### Retrieval and RAG

`retrieval/` provides keyword, semantic, graph-aware, and hybrid retrievers with
compatible result structures. Semantic retrieval uses a lightweight local
Sentence-Transformers model by default, keeping embeddings independent from
Gemini/Groq generation quotas; the model is configurable through
`CONCEPTSCAPE_EMBEDDING_MODEL`. `rag/` classifies queries as concept lookup,
relationship query, or question answering; assembles evidence; generates an
answer; and validates citation numbers before returning it.

### API and frontend

`api/service.py` exposes health, documents, YouTube registration, graph,
concepts, authenticated workspace/member management, persistent chat sessions,
pipeline jobs, pipeline execution, and grounded question endpoints. Every
workspace data endpoint requires a bearer token and `X-Workspace-ID` header.
The Next.js frontend provides document upload, pipeline monitoring, graph
exploration, source detail panels, cited chat history, login, and workspace
member management.

P2 product flows include document metadata/search/filtering, replacement with
archived versions, reprocessing, graph filters and neighborhood/path/
prerequisite queries, and renameable/deletable persistent chat sessions.

P3 learning flows use only verified graph/evidence data: cycle-safe learning
paths, concept progress/mastery, grounded explanation modes, evidence-backed
quiz generation and attempts, progress dashboards, and browser text-to-speech.

P4 quality tooling keeps raw normalized concepts in
`data/normalized_concepts_raw.json` and writes pedagogical filter decisions
into the filtered artefact audit. `scripts/quality_report.py` flags low
confidence/OCR-suspect items and near duplicates without mutating provenance.
Workspace review decisions are stored separately with an immutable audit trail.
Human significance labels are prepared and scored by
`scripts/significance_review.py`; precision, recall, and F1 exclude unlabelled
items rather than pretending pending judgements are correct or incorrect.

## Storage and reproducibility

The current local pipeline uses JSON artefacts:

- `output/ingestion_result.json`
- `output/preprocessed_chunks.json`
- `data/extracted_concepts.json`
- `data/normalized_concepts.json`
- `data/relationships.json`
- `data/graph_export.json`

Content hashes allow unchanged ingestion, extraction, and relationship work to
be reused. Failed LLM work is not cached. Run `python scripts/validate_artifacts.py`
after regeneration to verify IDs, provenance references, and graph consistency.
The canonical input list is `demo_corpus.json`; `run_pipeline.ps1` regenerates
the artefacts from the documents directory and validates the complete chain.

Authenticated product workspaces store their documents and generated artefacts
under `workspaces/<workspace-id>/`. Relational records are stored in
`conceptscape.db` by default or in the configured PostgreSQL database. The
schema is created and version-marked by `storage/migrations.py` at API startup.
Vector collections and local vector storage are also workspace-scoped. Remote
Qdrant uses separate `<workspace-id>_concepts` and `<workspace-id>_chunks`
collections; local fallback is development-only and must be disabled in
staging/production so connection failures cannot silently write ephemeral data.

## Local setup

1. Copy `.env.example` to `.env` and add provider credentials.
2. Run `./bootstrap.ps1` from PowerShell.
3. Run the pipeline scripts in order, or start the API with `python run_api.py`.
4. Run `./run_demo.ps1` after generated artefacts exist, then create an account
   at `/login` before uploading or asking questions.

Never commit `.env` or log API keys. Provider credentials must be rotated in
their provider dashboards if they were previously exposed; the application
only reads replacements from environment variables.

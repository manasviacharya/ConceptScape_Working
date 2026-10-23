---
name: conceptscape-pipeline
description: >-
  Use this skill when working on the ConceptScape educational capstone project. 
  It provides the strict architectural pipeline rules, technology choices (PaddleOCR, NetworkX), 
  and explicit boundaries (backend only, graph-focused RAG) to follow during implementation.
---

# ConceptScape Master Skill & Project Runbook

Project: **ConceptScape: A Knowledge Graph-Based Framework for Concept Extraction and Retrieval from Educational Content**

The central goal is to transform educational content into an explainable knowledge graph of concepts and relationships and use that graph for concept-based and graph-aware retrieval. ConceptScape is NOT a generic chatbot or NotebookLM clone.

## Core Pipeline Architecture
Educational Content → PDF/PPT/Image → Native Text OR PaddleOCR → Text Preprocessing → Chunking → Concept Extraction → Concept Normalization → Relationship Extraction → Knowledge Graph → Keyword+Semantic+Graph Retrieval → Hybrid Retrieval → Grounded RAG → Answer+Concepts+Relationships+Source Evidence

---

## SKILL 1: Repository / Codebase Inspection
Before modifying code:
1. Inspect the existing repository and relevant files.
2. Understand the existing architecture and identify what is already implemented.
3. Avoid rewriting working code unnecessarily. Preserve existing functionality unless explicitly required to change.
4. Check dependencies before adding new ones.
5. Modify only the files relevant to the current phase unless a dependency requires otherwise.

## SKILL 2: Phase Discipline
The implementation plan is the source of truth. When given a phase-specific task:
- Implement ONLY that phase. Do not silently implement future phases or introduce unrelated features.
- Do not redesign the architecture without justification or change fixed technology decisions.
- Do not modify future-phase behavior unnecessarily.
- At the end of every phase: test the implementation, verify acceptance criteria, inspect generated outputs, verify source traceability, report files changed, report what was completed, and report anything intentionally deferred. Do not mark complete if acceptance criteria are unmet.

## SKILL 3: Prompt Chunking / Task Decomposition
For large implementation tasks, internally decompose work into logical sub-tasks before editing files:
`Inspect → Plan → Implement → Validate → Test → Document`
Do not send huge monolithic changes blindly. Break implementation into logically testable units. Do not create unnecessary files merely to satisfy decomposition.

## SKILL 4: Configuration Management
All reusable configuration must be centralized in `config/settings.py` and `config/constants.py`.
- Include: file paths, model names, API settings, thresholds, chunk sizes, overlap, OCR thresholds, retrieval top-K, relationship taxonomy, query types, supported extensions.
- Do not hardcode configuration inside pipeline logic or API keys. Use `.env` for secrets.

## SKILL 5: Documentation Synchronization
Whenever an implementation phase changes the actual architecture:
1. Inspect if `architecture.md` is outdated and update where appropriate.
2. Keep documentation consistent with the actual implementation.
3. Do not invent features that are not implemented. The documentation must describe the real system.
4. Do not update documentation unnecessarily for non-architectural changes.

## SKILL 6: Architecture Consistency
Maintain clear separation of responsibilities:
- **Ingestion**: document loading and source extraction
- **OCR**: PaddleOCR text extraction from image/scanned content
- **Preprocessing**: cleaning, sentence processing, chunking
- **Extraction**: concepts and relationships
- **Normalization**: canonical concept resolution
- **Graph**: knowledge graph construction and queries
- **Retrieval**: keyword, semantic, graph and hybrid retrieval
- **Generation**: grounded answer generation
- **RAG**: pipeline orchestration
- **Storage**: persistent intermediate/output data
- **Evaluation**: metrics and experiments
Do not merge unrelated responsibilities into giant modules.

## SKILL 7: OCR / Document Processing
- **PaddleOCR ONLY**. Do not replace with EasyOCR, Tesseract, Google Vision, etc.
- For PDFs: if reliable native text exists (PyMuPDF), use it (`source_type: native_text`). Else render page and use PaddleOCR (`source_type: paddleocr`).
- Do not unnecessarily OCR pages with native text.
- Preserve useful OCR metadata (confidence, bounding boxes, reading/spatial order, page number). Raw extracted text must be retained separately from cleaned text.

## SKILL 8: Source Traceability / Provenance (NON-NEGOTIABLE)
Traceability chain: `Document → Page → Chunk → Concept / Relationship → Evidence`.
- Every concept and relationship must retain: document_id, document name, page, chunk_id(s), source evidence, confidence, model_used.
- Retrieval must trace results back to: `Query → Concept/Relationship → Evidence → Chunk → Page → Document`.
- Never detach extracted concepts from their source.

## SKILL 9: Concept Extraction
- Extract meaningful educational concepts. Do not extract every noun blindly.
- Every extracted concept must exist in the source material, have exact source evidence, have provenance, and have confidence/relevance metadata.
- Do not invent concepts. LLMs are supporting extraction tools, not the entire application.

## SKILL 10: Concept Normalization
- Support case-insensitive matching, singular/plural normalization, abbreviation handling, canonical naming, and duplicate merging (e.g., "Neural Network", "neural networks" → single node).
- Use `chunk_ids` for merged concepts. Do not discard provenance when merging.

## SKILL 11: Relationship Extraction
- Use controlled vocabulary: `related_to`, `part_of`, `depends_on`, `requires`, `produces`, `causes`, `used_for`, `example_of`, `prerequisite_of`, `associated_with`.
- If type is unclear, use `related_to`, but only when evidence supports a relationship.

## SKILL 12: Evidence-Grounded Graph Rule (NON-NEGOTIABLE)
- Every edge must be supported by source evidence.
- Do NOT create an edge just because concepts co-occur on a page/chunk or the LLM thinks they are generally related.
- For cross-chunk relationships, create an edge only when sufficient textual evidence supports it. If no reliable evidence exists: **DO NOT CREATE THE EDGE**. Prefer a smaller trustworthy graph over a large hallucinated one.

## SKILL 13: Graph Construction
- Node = Concept, Edge = Relationship. Initial implementation: NetworkX DiGraph.
- Relationship direction must remain semantically consistent (e.g., Photosynthesis → requires → Light Energy).
- **Node metadata**: canonical name, definition/context, source documents, source pages, chunk IDs, occurrence count, confidence, keywords.
- **Edge metadata**: source, target, relation type, evidence, pages, chunk IDs, documents, confidence, model used.

## SKILL 14: Graph Storage Abstraction
- Current MVP: NetworkX. Future: Neo4j.
- Use an abstraction (e.g., `BaseGraphStore`) so migrating `NetworkX → Neo4j` later does not require rewriting construction, queries, or retrieval.
- Do not introduce Neo4j prematurely.

## SKILL 15: Graph Queries
- Support reusable operations: get concept by name, neighbors, relationships, N-hop subgraph, shortest path, concepts from document/page/chunk, high-occurrence/centrality concepts.
- Queries should operate through the graph abstraction.

## SKILL 16: Retrieval
- Strategies: Keyword (exact/normalized/fuzzy), Semantic (sentence-transformers, local, FAISS/Chroma), Graph-Aware (neighbors/prerequisites/evidence), Hybrid (combine, rank, deduplicate).
- All retrievers must produce compatible result structures for evaluation.

## SKILL 17: Query Classification
- **Type A (Concept Lookup)**: e.g., "Photosynthesis"
- **Type B (Relationship Query)**: e.g., "What does photosynthesis require?"
- **Type C (Question Answering)**: e.g., "What is photosynthesis?"
Route retrieval and generation accordingly.

## SKILL 18: RAG / Grounded Generation
- RAG Flow: Query → Query Understanding → Concept Identification → Hybrid Retrieval → Evidence Assembly → Answer Generation.
- The LLM may only generate answers from retrieved evidence. Do not invent information. If evidence is unavailable, state so.
- Answers must preserve source references (concept, relationship, doc, page, chunk).

## SKILL 19: LLM Provider / Fallback
- Primary: Gemini. Fallback: Groq. Behavior: `Gemini → failure → Groq → failure → Graceful failure`.
- Always record `model_used`. Do not silently change models during evaluation.

## SKILL 20: Logging / Observability
- Maintain clear pipeline progress logging (e.g., `✓ Ingestion complete, ✓ X chunks created`, etc.).
- Identify stage, counts, warnings, failures, and model used. Do not hide unexpected programming errors.

## SKILL 21: Error Handling
- User-facing execution must fail gracefully (e.g., unsupported files, no text, OCR failure, etc.).
- Use specific exception handling + structured logging + clear error context. Do not use broad exception handling to hide bugs during development.

## SKILL 22: Caching / Performance
- Avoid unnecessary reprocessing using `document hash` to detect unchanged documents (OCR cache, Preprocessing cache, Extraction cache, Graph reuse).
- Do not regenerate expensive outputs when the source has not changed. Correctness comes first.

## SKILL 23: Data Modeling
- Use structured schemas (dataclasses, Pydantic, JSON schemas) for intermediate outputs (Document, Page, Chunk, Concept, Relationship, Graph, Retrieval Result).

## SKILL 24: Testing After Every Phase
- Validation is mandatory: `Implement → Run tests → Run sample documents → Inspect outputs → Verify provenance → Verify acceptance criteria`. Test both native-text and scanned documents.

## SKILL 25: Evaluation
- Eventual coverage: OCR (CER/WER), Extraction (Precision/Recall/F1), Retrieval (Precision@K/Recall@K/MRR), Graph (node/edge precision & recall).

## SKILL 26: Retrieval Experiments
- Preserve ability to compare: Keyword vs Semantic vs Graph-Aware vs Hybrid.
- Do not invent evaluation results.

## SKILL 27: Security
- Never hardcode or log API keys. Use `.env`. Respect `.gitignore`.

## SKILL 28: Code Quality
- Maintain type hints, docstrings, meaningful naming, modular single-responsibility functions, no duplicated logic, centralized config. Prefer readable code over clever code.

## SKILL 29: Documentation / Architecture Auto-Update
- Update `architecture.md` when implementation changes architecture. Do not retain obsolete technology references.

## SKILL 30: Endpoint / Interface Design
- Keep APIs thin. Endpoints call services, no business logic in route handlers. Use consistent schemas preserving provenance. Do not implement endpoints prematurely.

## SKILL 31: Obsidian / Graphify Project Knowledge
- Keep project-knowledge artifacts synced with implementation. Maintain links. Do not treat Obsidian/Graphify as runtime.

## SKILL 32: UI / Visualization Boundary
- Backend remains separate. Streamlit / PyVis are DEFERRED. Do not duplicate backend logic in UI. Do not start UI during backend-only phases.

## SKILL 33: Future Extension Discipline
- Do not prematurely implement learning paths, quizzes, flashcards, etc. Architecture should allow them later.

## SKILL 34: Fixed Project Decisions (FROZEN)
- OCR: PaddleOCR | PDF: PyMuPDF | PPT: python-pptx | Graph: NetworkX initially | Embeddings: sentence-transformers | Vector: FAISS/Chroma | LLM: Gemini (Primary), Groq (Fallback) | UI: Streamlit (later)
- Never silently substitute.

## SKILL 35: Change Control & Agent Behavior
- **Behavior**: `Understand first → Inspect existing code → Follow frozen architecture → Implement only requested phase → Preserve provenance → Test → Update docs → Report`.
- **Change Control**: Before changing architecture/deps/schemas: check plan and SKILL.md. Prefer existing architecture. No convenient new deps. Report conflicts explicitly.
- Optimize for correctness, reproducibility, explainability, modularity, maintainability, and simplicity. Not for unnecessary features.

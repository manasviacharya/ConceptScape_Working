# Phase 2 — Requirement traceability and implementation audit

Status labels use the requested vocabulary and are based on executable evidence where available.

| ID | Requirement | Evidence | Status | Test/evidence gap |
|---|---|---|---|---|
| R1 | PDF native extraction with OCR fallback | `ingestion/pdf_parser.py`, `ocr_engine.py`, PyMuPDF/PaddleOCR imports | PARTIAL | Dependencies unavailable; no current PDF artifact in generated state |
| R2 | PPTX slide extraction | `ingestion/ppt_parser.py`; current ingestion has 3 PPT resources | PASS (code/current artifact) | Native parser output not independently re-executed |
| R3 | Image/scanned OCR | `image_parser.py`, PaddleOCR engine | BLOCKED | PaddleOCR/PyMuPDF dependencies unavailable |
| R4 | validation, limits, unsupported/corrupt input | `_safe_name`, `_content_type_error`, upload size checks in `api/service.py` | NOT TESTED | API cannot import in current environment |
| R5 | cleaning, chunking, source metadata | `preprocessing/*`, current 53 chunks | PASS (code/current artifact) | No pytest suite execution |
| R6 | concept evidence grounding | `extraction/extractor.py::_verify_evidence` and prompt/schema | PASS (unit-like direct suite) | Provider-backed extraction not run |
| R7 | normalization, aliases, Unicode/plurals | `normalization/normalizer.py`; relationship suite | PASS | Coverage is custom direct suite, not pytest |
| R8 | semantic fusion and false-merge guards | `normalization/semantic_fusion.py`; relationship suite checks distinct concepts | PARTIAL | Frozen BGE-M3 requirement conflicts with current MiniLM default; no current semantic run |
| R9 | controlled, evidence-backed relationships | `relationships/*`; 27/27 direct checks | PASS (isolated behavior) | Current artifact has 0 relationships; corpus workflow not verified |
| R10 | graph abstraction and queries | `graph/graph_store.py`, `memory_store.py`, `neo4j_store.py` | PARTIAL | NetworkX requirement in project skill vs current custom stores; live Neo4j unavailable/not tested |
| R11 | keyword/semantic/graph/hybrid retrieval | `retrieval/retrievers.py`; 21/21 direct checks | PASS (isolated behavior) | Real vector index/model not executed |
| R12 | grounded RAG and citations | `rag/*`; 28/28 direct checks | PASS (isolated behavior) | Provider-backed answer path blocked |
| R13 | Gemini primary/Groq fallback | `llm_provider.py`, config | NOT TESTED | No credentials/provider execution |
| R14 | API/frontend integration | FastAPI routes and Next.js API client exist | BLOCKED | FastAPI missing; frontend dependencies/build unavailable |
| R15 | persistence/restart/workspace behavior | `storage/*`, `api/service.py`, workspace paths | NOT TESTED | Database service and API unavailable |
| R16 | reproducible evaluation | `evaluation/*`, review fixtures exist | PARTIAL | `data/evaluation_results.json` and `data/ablation_results.json` are absent |
| R17 | artifact consistency | `scripts/validate_artifacts.py` | FAIL | Executed validator reports extraction/normalization `subject_id` mismatch |

## Current generated-state facts

The checked-out artifacts currently contain 3 PPT resources, 53 chunks, 93 extracted mentions, 80 normalized concepts, and 0 relationships. `data/evaluation_results.json` and `data/ablation_results.json` do not exist. The historical `CONCEPTSCAPE_PAPER_CONTEXT.md` numbers must not be reported as results from this checkout.

## Priority actions

1. Regenerate the full canonical corpus with the required dependencies and configured providers; do not hand-edit generated JSON.
2. Resolve the embedding-model decision against the frozen project requirement and update configuration/documentation consistently.
3. Install and run the declared test/build toolchain in a network-enabled environment.
4. Re-run artifact validation and all real API/integration workflows.


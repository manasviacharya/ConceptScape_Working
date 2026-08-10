# ConceptScape — Architecture Documentation

## Overview
ConceptScape is an AI-powered multimodal learning workspace that organizes educational resources around concepts rather than documents.

This documentation outlines the current implementation of the **Resource Ingestion** and **Concept Extraction** layers.

## Current Pipeline

```text
documents/ (PDF, PPT)
     │
     ▼
1. INGESTION LAYER
   (run_ingestion.py)
   - Parses files via PyMuPDF and python-pptx
   - Preserves page/slide boundaries
   - Normalizes to a Common Structured Representation
     │
     ▼
   output/ingestion_result.json
     │
     ▼
2. EXTRACTION LAYER
   (run_extraction.py)
   - Chunks ingested content
   - Uses Groq (llama-3.3-70b-versatile) to extract concepts
   - Extracts Definition, Keywords, Relationships
   - Attaches strict Source Provenance metadata
     │
     ▼
   data/extracted_concepts.json
```

## Module Architecture

### 1. Ingestion (`ingestion/`)
* **`base_parser.py`**: Abstract interface for parsers (`can_handle`, `parse`).
* **`pdf_parser.py`**: Implementation for parsing PDFs using `PyMuPDF`.
* **`ppt_parser.py`**: Implementation for parsing PPT/PPTX using `python-pptx`.
* **`dispatcher.py`**: Scans the input directory and automatically routes files to the correct parser.
* **`models.py`**: Dataclasses for `IngestedResource` and `ContentChunk`.

### 2. Extraction (`extraction/`)
* **`extractor.py`**: Main logic that takes chunks of text, interfaces with the Groq API for LLM inference, and maps the response into our required schema.
* **`models.py`**: Pydantic models (`ExtractedConcept`, `Relationship`, `ExtractionResult`) used to enforce strict JSON schemas on the LLM output.

## Future Stages (Planned)
* **Embedding**: Converting extracted concepts to vector embeddings (BGE-M3).
* **Vector DB**: Storing embeddings in Qdrant for Cosine similarity matching.
* **Knowledge Graph**: Building an interactive graph using Neo4j and React Flow.
* **Merging**: Identifying similar concept mentions across different documents and merging them into unified concept nodes.

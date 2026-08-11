# ConceptScape — Architecture Documentation

## Overview
ConceptScape is an AI-powered multimodal learning workspace that organizes educational resources around concepts rather than documents.

This documentation outlines the current implementation of the **Resource Ingestion** and **Concept Extraction** layers.

## Current Pipeline

```text
PDF (PyMuPDF)
 │
 ▼
Structured text ──────────┐
                          │
PPT (python-pptx)         │
 │                        │
 ▼                        │
Structured text ──────────┼──→ Gemini 2.5 Flash
                          │        │
Image (EasyOCR)           │        ▼
 │                        │   Concept Extraction
 ▼                        │        │
Structured OCR text ──────┘        ▼
                              Concept Mentions
                                   │
                                   ▼
                              data/extracted_concepts.json
```

## Module Architecture

### 1. Ingestion (`ingestion/`)
* **`base_parser.py`**: Abstract interface for parsers (`can_handle`, `parse`).
* **`pdf_parser.py`**: Implementation for parsing PDFs using `PyMuPDF`.
* **`ppt_parser.py`**: Implementation for parsing PPT/PPTX using `python-pptx`.
* **`image_parser.py`**: Implementation for parsing images (`.png`, `.jpg`, `.jpeg`, `.webp`) using `EasyOCR`. Includes OpenCV (`cv2`) preprocessing (BGR loading, 1200px resizing, and CLAHE contrast normalization) to handle high-resolution photos reliably. Outputs compact `[x1, y1, x2, y2]` bounding boxes in original image coordinates and filters noise using a confidence threshold.
* **`dispatcher.py`**: Scans the input directory and automatically routes files to the correct parser.
* **`models.py`**: Dataclasses for `IngestedResource` and `ContentChunk`.

### 2. Extraction (`extraction/`)
* **`extractor.py`**: Main logic that takes chunks of text, interfaces with Gemini 2.5 Flash via `google-genai` SDK, and maps the response into our required schema.
* **`models.py`**: Pydantic models (`ExtractedConcept`, `Relationship`, `ExtractionResult`) used to enforce strict JSON schemas on the LLM output.

## Future Stages (Planned)
* **Embedding**: Converting extracted concepts to vector embeddings (BGE-M3).
* **Vector DB**: Storing embeddings in Qdrant for Cosine similarity matching.
* **Knowledge Graph**: Building an interactive graph using Neo4j and React Flow.
* **Merging**: Identifying similar concept mentions across different documents and merging them into unified concept nodes.

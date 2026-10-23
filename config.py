from typing import Optional

from dotenv import find_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        "env_file": find_dotenv(),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "env_prefix": "CONCEPTSCAPE_",
    }

    # secrets
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # paths
    documents_dir: str = "documents"
    output_dir: str = "output"
    data_dir: str = "data"

    # OCR (PaddleOCR 3.x with ONNX runtime backend)
    ocr_target_width: int = 1200
    ocr_min_confidence: float = 0.3
    ocr_language: str = "en"

    # YouTube transcripts — caption snippets are a few words each, so they are
    # grouped into segments of roughly this length before chunking
    youtube_segment_seconds: int = 45

    # PDF OCR fallback
    pdf_native_text_min_chars: int = 50
    pdf_ocr_render_dpi: int = 200
    enable_pdf_ocr_fallback: bool = True

    # Gemini
    gemini_model: str = "gemini-3.6-flash"
    gemini_temperature: float = 0.1
    gemini_max_retries: int = 4
    gemini_retry_base_delay: float = 3.0
    # after this many rate-limited chunks, stop using Gemini for the run
    gemini_rate_limit_trip_after: int = 2

    # Groq
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.1

    # extraction — chunks shorter than this are skipped (titles, headers)
    extraction_min_chunk_chars: int = 50
    # drop concepts whose evidence span cannot be found in the source
    # Switches the extraction prompt between grounded (evidence required) and
    # a conventional ungrounded instruction — the ablation baseline.
    extraction_grounded_prompt: bool = True
    require_evidence: bool = True
    min_concept_confidence: float = 0.0

    # Neo4j
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # embeddings / vector store
    embedding_model: str = "BAAI/bge-m3"
    qdrant_url: str = ""            # empty -> embedded local mode (no server)
    qdrant_api_key: str = ""
    qdrant_path: str = "qdrant_data"
    qdrant_timeout: int = 120
    # use an embedded local Qdrant when the cloud instance is unreachable
    qdrant_allow_local_fallback: bool = True
    qdrant_upsert_batch: int = 16
    retrieval_top_k: int = 8
    semantic_score_threshold: float = 0.30

    # hybrid fusion weights per retriever
    weight_keyword: float = 1.0
    weight_semantic: float = 1.0
    weight_graph: float = 0.8

    # API service
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:3111"]

    upload_max_bytes: int = 50_000_000

    # RAG
    rag_max_citations: int = 12
    rag_evidence_per_concept: int = 2
    rag_chunk_char_limit: int = 600
    rag_thin_evidence_threshold: int = 3

    # fall back to the in-memory graph when Neo4j cannot be reached
    graph_allow_memory_fallback: bool = True

    # relationships — controlled vocabulary; anything outside this is rejected
    relationship_types: list[str] = [
        "related_to", "part_of", "depends_on", "requires", "produces",
        "causes", "used_for", "example_of", "prerequisite_of",
    ]

    # cross-chunk linking — large documents are batched so the JSON response
    # stays small enough for provider-side validation
    cross_chunk_max_concepts: int = 15
    cross_chunk_anchor_concepts: int = 4

    # normalization
    # merge the same concept across documents into one node
    normalize_cross_document: bool = True
    # semantic fusion — merges concepts lexical matching cannot bridge
    fusion_enabled: bool = True
    # A coarse pre-filter only — the guards in semantic_fusion.py decide.
    # 0.92 was too strict: the target pair (Mini-Batch SGD / Mini-Batch
    # Stochastic Gradient Descent) sits at 0.85.
    fusion_similarity_threshold: float = 0.80
    fusion_min_token_overlap: float = 0.5
    normalize_strip_parentheticals: bool = True
    normalize_fold_plurals: bool = True

    # preprocessing — chunking
    chunk_target_chars: int = 1200
    chunk_overlap_chars: int = 150
    chunk_min_chars: int = 100

    # preprocessing — cleaning
    clean_normalize_unicode: bool = True
    clean_dehyphenate: bool = True
    clean_remove_headers_footers: bool = True
    clean_remove_page_numbers: bool = True
    clean_normalize_bullets: bool = True
    clean_join_ocr_lines: bool = True
    header_footer_min_page_ratio: float = 0.6

    # logging
    log_level: str = "INFO"
    log_format: str = "[%(levelname)s] %(message)s"


settings = Settings()

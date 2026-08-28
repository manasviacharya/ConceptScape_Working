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
    require_evidence: bool = True
    min_concept_confidence: float = 0.0

    # Neo4j
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # relationships — controlled vocabulary; anything outside this is rejected
    relationship_types: list[str] = [
        "related_to", "part_of", "depends_on", "requires", "produces",
        "causes", "used_for", "example_of", "prerequisite_of",
    ]

    # normalization
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

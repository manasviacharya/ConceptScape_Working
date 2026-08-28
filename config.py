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

    # OCR (PaddleOCR)
    ocr_target_width: int = 1200
    ocr_min_confidence: float = 0.3
    ocr_language: str = "en"
    ocr_use_angle_cls: bool = True
    ocr_use_gpu: bool = False

    # PDF OCR fallback
    pdf_native_text_min_chars: int = 50
    pdf_ocr_render_dpi: int = 200
    enable_pdf_ocr_fallback: bool = True

    # Gemini
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1
    gemini_max_retries: int = 3
    gemini_retry_base_delay: float = 2.0

    # Groq
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.1

    # logging
    log_level: str = "INFO"
    log_format: str = "[%(levelname)s] %(message)s"


settings = Settings()

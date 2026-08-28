from typing import Optional

from dotenv import find_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": find_dotenv(), "env_file_encoding": "utf-8", "extra": "ignore"}

    # secrets
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # paths
    documents_dir: str = "documents"
    output_dir: str = "output"
    data_dir: str = "data"
    cache_dir: str = "cache"

    # OCR
    ocr_target_width: int = 1200
    ocr_clahe_clip_limit: float = 2.0
    ocr_min_confidence: float = 0.3
    ocr_languages: list[str] = ["en"]
    ocr_gpu: bool = False

    # Gemini
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1
    gemini_max_retries: int = 3
    gemini_retry_base_delay: float = 2.0

    # Groq
    groq_model: str = "llama-3.3-70b-versatile"

    # logging
    log_level: str = "INFO"
    log_format: str = "[%(levelname)s] %(message)s"


settings = Settings()

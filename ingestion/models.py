from dataclasses import dataclass
from typing import Any


@dataclass
class ContentChunk:
    chunk_id: str
    source_type: str
    location_type: str
    location_number: int
    text: str
    content_hash: str = ""
    extraction_method: str = ""
    ocr_regions: list[dict[str, Any]] | None = None

@dataclass
class IngestedResource:
    resource_id: str
    resource_type: str
    filename: str
    subject_id: str
    content: list[ContentChunk]
    content_hash: str = ""

@dataclass
class IngestionResult:
    subject_id: str
    resources: list[IngestedResource]
    ingestion_timestamp: str

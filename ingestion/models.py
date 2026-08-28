from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ContentChunk:
    chunk_id: str
    source_type: str
    location_type: str
    location_number: int
    text: str
    content_hash: str = ""
    extraction_method: str = ""
    ocr_regions: Optional[List[Dict[str, Any]]] = None

@dataclass
class IngestedResource:
    resource_id: str
    resource_type: str
    filename: str
    subject_id: str
    content: List[ContentChunk]
    content_hash: str = ""

@dataclass
class IngestionResult:
    subject_id: str
    resources: List[IngestedResource]
    ingestion_timestamp: str

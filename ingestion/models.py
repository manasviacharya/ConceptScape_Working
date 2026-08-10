from dataclasses import dataclass
from typing import List

@dataclass
class ContentChunk:
    content_id: str
    location_type: str
    location_number: int
    text: str

@dataclass
class IngestedResource:
    resource_id: str
    resource_type: str
    filename: str
    subject_id: str
    content: List[ContentChunk]

@dataclass
class IngestionResult:
    subject_id: str
    resources: List[IngestedResource]
    ingestion_timestamp: str

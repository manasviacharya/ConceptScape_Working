from dataclasses import dataclass


@dataclass
class TextChunk:
    chunk_id: str
    resource_id: str
    filename: str
    source_type: str
    extraction_method: str
    location_type: str
    location_number: int
    text: str
    raw_text: str
    char_count: int
    sentence_count: int
    content_hash: str

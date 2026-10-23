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
    # Full UNCLEANED text of the page/slide this chunk came from.
    #
    # Deliberately the whole page, not a per-chunk slice: cleaning deletes and
    # merges lines, so cleaned sentences cannot be mapped back to raw sentences
    # by position. The previous attempt paired two independently-split lists by
    # index and produced spans that did not occur in the source at all.
    # A page-level superset is verifiable — an evidence span can be checked for
    # membership in it — which is what grounding and citations actually need.
    raw_page_text: str
    char_count: int
    sentence_count: int
    content_hash: str

import hashlib
import logging
from typing import List

from config import settings
from preprocessing.models import TextChunk


def chunk_page(
    sentences: List[str],
    raw_sentences: List[str],
    parent_chunk_id: str,
    resource_id: str,
    filename: str,
    source_type: str,
    extraction_method: str,
    location_type: str,
    location_number: int,
) -> List[TextChunk]:
    if not sentences:
        return []

    target = settings.chunk_target_chars
    overlap_chars = settings.chunk_overlap_chars
    min_chars = settings.chunk_min_chars

    chunks: List[TextChunk] = []
    current_sents: List[str] = []
    current_raw: List[str] = []
    current_len = 0
    chunk_index = 0

    def _make_chunk(sents: List[str], raws: List[str], idx: int) -> TextChunk:
        text = " ".join(sents)
        raw_text = " ".join(raws)
        return TextChunk(
            chunk_id=f"{parent_chunk_id}_c{idx:03d}",
            resource_id=resource_id,
            filename=filename,
            source_type=source_type,
            extraction_method=extraction_method,
            location_type=location_type,
            location_number=location_number,
            text=text,
            raw_text=raw_text,
            char_count=len(text),
            sentence_count=len(sents),
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    for i, sent in enumerate(sentences):
        sent_len = len(sent)

        if sent_len > target:
            logging.warning(f"Oversized sentence ({sent_len} chars) in {parent_chunk_id} — emitting as standalone chunk")

        if current_sents and current_len + sent_len + 1 > target:
            chunks.append(_make_chunk(current_sents, current_raw, chunk_index))
            chunk_index += 1

            # Overlap: carry trailing whole sentences from previous chunk
            overlap_sents: List[str] = []
            overlap_raws: List[str] = []
            overlap_len = 0
            for j in range(len(current_sents) - 1, -1, -1):
                s = current_sents[j]
                if overlap_len + len(s) + 1 > overlap_chars:
                    break
                overlap_sents.insert(0, s)
                overlap_raws.insert(0, current_raw[j])
                overlap_len += len(s) + 1

            current_sents = list(overlap_sents)
            current_raw = list(overlap_raws)
            current_len = sum(len(s) for s in current_sents) + max(0, len(current_sents) - 1)

        current_sents.append(sent)
        current_raw.append(raw_sentences[i])
        current_len += sent_len + (1 if len(current_sents) > 1 else 0)

    if current_sents:
        # Merge short trailing chunk into previous if possible
        trailing_text_len = sum(len(s) for s in current_sents) + max(0, len(current_sents) - 1)
        if trailing_text_len < min_chars and chunks:
            prev = chunks[-1]
            merged_sents = prev.text.split(" ")  # not ideal but we track properly below
            merged_text = prev.text + " " + " ".join(current_sents)
            merged_raw = prev.raw_text + " " + " ".join(current_raw)
            chunks[-1] = TextChunk(
                chunk_id=prev.chunk_id,
                resource_id=prev.resource_id,
                filename=prev.filename,
                source_type=prev.source_type,
                extraction_method=prev.extraction_method,
                location_type=prev.location_type,
                location_number=prev.location_number,
                text=merged_text,
                raw_text=merged_raw,
                char_count=len(merged_text),
                sentence_count=prev.sentence_count + len(current_sents),
                content_hash=hashlib.sha256(merged_text.encode("utf-8")).hexdigest(),
            )
        else:
            chunks.append(_make_chunk(current_sents, current_raw, chunk_index))

    return chunks

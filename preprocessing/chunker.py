import hashlib
import logging
from dataclasses import replace
from typing import List

from config import settings
from preprocessing.models import TextChunk


def chunk_page(
    sentences: List[str],
    raw_page_text: str,
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
    current_len = 0
    chunk_index = 0

    def _make_chunk(sents: List[str], idx: int) -> TextChunk:
        text = " ".join(sents)
        return TextChunk(
            chunk_id=f"{parent_chunk_id}_c{idx:03d}",
            resource_id=resource_id,
            filename=filename,
            source_type=source_type,
            extraction_method=extraction_method,
            location_type=location_type,
            location_number=location_number,
            text=text,
            raw_page_text=raw_page_text,
            char_count=len(text),
            sentence_count=len(sents),
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    # How many leading sentences of current_sents were carried over as overlap.
    # They already exist in the previous chunk, so the trailing-merge below must
    # not append them again — doing so duplicates text and inflates the count.
    overlap_count = 0

    for sent in sentences:
        sent_len = len(sent)

        # A sentence longer than the target becomes its own chunk. Flush what is
        # pending first, otherwise it gets bundled with carried-over overlap and
        # the result is larger still — the opposite of "standalone".
        if sent_len > target:
            if current_sents:
                chunks.append(_make_chunk(current_sents, chunk_index))
                chunk_index += 1
            logging.warning(
                f"Oversized sentence ({sent_len} chars) in {parent_chunk_id} — emitting as standalone chunk"
            )
            chunks.append(_make_chunk([sent], chunk_index))
            chunk_index += 1
            current_sents = []
            current_len = 0
            overlap_count = 0
            continue

        if current_sents and current_len + sent_len + 1 > target:
            chunks.append(_make_chunk(current_sents, chunk_index))
            chunk_index += 1

            # Overlap: carry trailing whole sentences from the previous chunk
            overlap_sents: List[str] = []
            overlap_len = 0
            for j in range(len(current_sents) - 1, -1, -1):
                s = current_sents[j]
                if overlap_len + len(s) + 1 > overlap_chars:
                    break
                overlap_sents.insert(0, s)
                overlap_len += len(s) + 1

            current_sents = list(overlap_sents)
            overlap_count = len(overlap_sents)
            current_len = sum(len(s) for s in current_sents) + max(0, len(current_sents) - 1)

        current_sents.append(sent)
        current_len += sent_len + (1 if len(current_sents) > 1 else 0)

    if current_sents:
        # Only the sentences not already carried in the previous chunk are new.
        new_sents = current_sents[overlap_count:]
        if not new_sents:
            return chunks

        trailing_len = sum(len(s) for s in new_sents) + max(0, len(new_sents) - 1)
        # Only absorb the short tail if the previous chunk has room. Without this
        # guard a stray trailing sentence gets appended to a chunk that is already
        # at (or over) target — including an oversized standalone sentence.
        can_absorb = bool(chunks) and (chunks[-1].char_count + trailing_len + 1) <= target
        if trailing_len < min_chars and can_absorb:
            prev = chunks[-1]
            merged_text = prev.text + " " + " ".join(new_sents)
            chunks[-1] = replace(
                prev,
                text=merged_text,
                char_count=len(merged_text),
                sentence_count=prev.sentence_count + len(new_sents),
                content_hash=hashlib.sha256(merged_text.encode("utf-8")).hexdigest(),
            )
        else:
            chunks.append(_make_chunk(current_sents, chunk_index))

    return chunks

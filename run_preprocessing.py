import json
import logging
import os
from dataclasses import asdict

from config import settings
from logging_setup import configure_logging
from preprocessing.cleaner import clean_text
from preprocessing.splitter import split_sentences
from preprocessing.chunker import chunk_page
from preprocessing.models import TextChunk


def main():
    configure_logging()

    INPUT_FILE = os.path.join(settings.output_dir, "ingestion_result.json")
    OUTPUT_FILE = os.path.join(settings.output_dir, "preprocessed_chunks.json")

    logging.info("ConceptScape Preprocessing Pipeline starting...")
    logging.info(f"Input: {INPUT_FILE}")

    if not os.path.exists(INPUT_FILE):
        logging.error(f"Ingestion result not found: {INPUT_FILE}")
        raise FileNotFoundError(INPUT_FILE)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        ingestion_data = json.load(f)

    all_chunks = []
    subject_id = ingestion_data.get("subject_id", "")

    for resource in ingestion_data.get("resources", []):
        resource_id = resource.get("resource_id", "")
        resource_type = resource.get("resource_type", "")
        filename = resource.get("filename", "")
        content_list = resource.get("content", [])

        # Collect all page texts for header/footer detection (PDF only)
        all_page_texts = None
        if resource_type == "pdf":
            all_page_texts = [c.get("text", "") for c in content_list]

        page_count = len(content_list)
        resource_chunks = []

        for page_idx, content_chunk in enumerate(content_list):
            raw_page_text = content_chunk.get("text", "")
            if not raw_page_text.strip():
                continue

            parent_chunk_id = content_chunk.get("chunk_id", "")
            extraction_method = content_chunk.get("extraction_method", "")
            location_type = content_chunk.get("location_type", "")
            location_number = content_chunk.get("location_number", 0)
            source_type = content_chunk.get("source_type", resource_type)

            cleaned = clean_text(
                raw_page_text,
                extraction_method=extraction_method,
                all_page_texts=all_page_texts,
                page_index=page_idx,
            )

            if not cleaned.strip():
                logging.warning(f"Cleaning removed all text from {filename} {location_type} {location_number}")
                continue

            sentences = split_sentences(cleaned)

            chunks = chunk_page(
                sentences=sentences,
                raw_page_text=raw_page_text,
                parent_chunk_id=parent_chunk_id,
                resource_id=resource_id,
                filename=filename,
                source_type=source_type,
                extraction_method=extraction_method,
                location_type=location_type,
                location_number=location_number,
            )

            resource_chunks.extend(chunks)

        if resource_chunks:
            chars = [c.char_count for c in resource_chunks]
            logging.info(
                f"{filename}: {page_count} pages -> {len(resource_chunks)} chunks, "
                f"{sum(c.sentence_count for c in resource_chunks)} sentences, "
                f"chars mean={sum(chars)//len(chars)} min={min(chars)} max={max(chars)}"
            )

        all_chunks.extend(resource_chunks)

    logging.info(f"\nTotal chunks: {len(all_chunks)}")

    os.makedirs(settings.output_dir, exist_ok=True)
    output = {
        "subject_id": subject_id,
        "chunks": [asdict(c) for c in all_chunks],
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logging.info(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

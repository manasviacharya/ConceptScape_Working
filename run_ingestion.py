import json
import logging
import os
from dataclasses import asdict

from config import settings
from logging_setup import configure_logging
from ingestion.dispatcher import IngestionDispatcher

def main():
    configure_logging()

    SUBJECT_ID = "subject_001"
    OUTPUT_FILE = os.path.join(settings.output_dir, "ingestion_result.json")

    logging.info("ConceptScape Ingestion Pipeline starting...")
    logging.info(f"Documents folder: {settings.documents_dir}/")
    logging.info(f"Subject: {SUBJECT_ID}")

    if not os.path.isdir(settings.documents_dir):
        raise FileNotFoundError(f"Documents folder not found: {settings.documents_dir}")

    dispatcher = IngestionDispatcher()
    result, failed_files = dispatcher.run(settings.documents_dir, SUBJECT_ID)

    logging.info("\nINGESTION COMPLETE")

    pdf_resources = [r for r in result.resources if r.resource_type == "pdf"]
    ppt_resources = [r for r in result.resources if r.resource_type == "ppt"]
    image_resources = [r for r in result.resources if r.resource_type == "image"]

    logging.info(f"Resources: {len(result.resources)} succeeded, {len(failed_files)} failed")

    logging.info("\nResources Summary:")
    for r in pdf_resources:
        native_count = sum(1 for c in r.content if c.extraction_method == "native_text")
        ocr_count = sum(1 for c in r.content if c.extraction_method == "paddleocr")
        logging.info(f"  ✓ PDF: {r.filename} ({len(r.content)} pages: {native_count} native_text, {ocr_count} paddleocr)")
    for r in ppt_resources:
        logging.info(f"  ✓ PPT: {r.filename} ({len(r.content)} slides)")
    for r in image_resources:
        regions_count = len(r.content[0].ocr_regions) if (r.content and r.content[0].ocr_regions) else 0
        logging.info(f"  ✓ image: {r.filename} ({regions_count} text regions detected)")

    if failed_files:
        logging.warning("\nFailed resources:")
        for fname, reason in failed_files:
            logging.warning(f"  ✗ {fname} — {reason}")

    os.makedirs(settings.output_dir, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

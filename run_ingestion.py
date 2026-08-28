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

    dispatcher = IngestionDispatcher()
    result = dispatcher.run(settings.documents_dir, SUBJECT_ID)

    logging.info("\nINGESTION COMPLETE")
    logging.info(f"Total resources processed: {len(result.resources)}")

    pdf_resources = [r for r in result.resources if r.resource_type == "pdf"]
    ppt_resources = [r for r in result.resources if r.resource_type == "ppt"]
    image_resources = [r for r in result.resources if r.resource_type == "image"]

    logging.info("\nResources Summary:")
    for r in pdf_resources:
        logging.info(f"  ✓ PDF: {r.filename} ({len(r.content)} pages)")
    for r in ppt_resources:
        logging.info(f"  ✓ PPT: {r.filename} ({len(r.content)} slides)")
    for r in image_resources:
        regions_count = len(r.content[0].ocr_regions) if (r.content and r.content[0].ocr_regions) else 0
        logging.info(f"  ✓ image: {r.filename} ({regions_count} text regions detected)")

    os.makedirs(settings.output_dir, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

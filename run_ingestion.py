import os
import json
import logging
from dataclasses import asdict
from pathlib import Path

from ingestion.dispatcher import IngestionDispatcher

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s'
    )

def main():
    setup_logging()
    
    DOCUMENTS_DIR = "documents"
    SUBJECT_ID = "subject_001"
    OUTPUT_DIR = "output"
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ingestion_result.json")
    
    logging.info("ConceptScape Ingestion Pipeline starting...")
    logging.info(f"Documents folder: {DOCUMENTS_DIR}/")
    logging.info(f"Subject: {SUBJECT_ID}")
    
    dispatcher = IngestionDispatcher()
    result = dispatcher.run(DOCUMENTS_DIR, SUBJECT_ID)
    
    logging.info("\nINGESTION COMPLETE")
    logging.info(f"Total resources processed: {len(result.resources)}")
    
    # Categorize resources by type
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

    # Save output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        
    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

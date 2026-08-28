import json
import logging
import os

from config import settings
from logging_setup import configure_logging
from extraction.extractor import ConceptExtractor

def main():
    configure_logging()

    INPUT_FILE = os.path.join(settings.output_dir, "ingestion_result.json")
    OUTPUT_FILE = os.path.join(settings.data_dir, "extracted_concepts.json")

    if not os.path.exists(INPUT_FILE):
        logging.error(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        ingestion_data = json.load(f)

    logging.info("ConceptScape Extraction Pipeline starting...")
    logging.info(f"Subject: {ingestion_data.get('subject_id')}")

    try:
        extractor = ConceptExtractor()
    except ValueError as e:
        logging.error(str(e))
        logging.info("Please create a .env file with GEMINI_API_KEY")
        return

    all_concepts = extractor.process_ingestion_result(ingestion_data)

    os.makedirs(settings.data_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"concepts": all_concepts}, f, indent=2, ensure_ascii=False)

    pdf_concepts = sum(1 for c in all_concepts if c.get("source_reference", {}).get("resource_type") == "pdf")
    ppt_concepts = sum(1 for c in all_concepts if c.get("source_reference", {}).get("resource_type") == "ppt")
    image_concepts = sum(1 for c in all_concepts if c.get("source_reference", {}).get("resource_type") == "image")

    logging.info("\n==================================================")
    logging.info("INGESTION + CONCEPT EXTRACTION COMPLETE")
    logging.info("==================================================")
    logging.info(f"Subject: {ingestion_data.get('subject_id')}")
    logging.info("\nConcept mentions extracted by source type:")
    logging.info(f"  PDF: {pdf_concepts}")
    logging.info(f"  PPT: {ppt_concepts}")
    logging.info(f"  Images: {image_concepts}")
    logging.info(f"  Total: {len(all_concepts)}")
    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

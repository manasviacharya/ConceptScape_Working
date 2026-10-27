import json
import logging
import os

from config import settings
from logging_setup import configure_logging
from extraction.extractor import ConceptExtractor

def main():
    configure_logging()

    INPUT_FILE = os.path.join(settings.output_dir, "preprocessed_chunks.json")
    OUTPUT_FILE = os.path.join(settings.data_dir, "extracted_concepts.json")

    if not os.path.exists(INPUT_FILE):
        logging.error(f"Input file not found: {INPUT_FILE}")
        raise FileNotFoundError(INPUT_FILE)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        preprocessed_data = json.load(f)

    logging.info("ConceptScape Extraction Pipeline starting...")
    logging.info(f"Subject: {preprocessed_data.get('subject_id')}")

    try:
        extractor = ConceptExtractor()
    except ValueError as e:
        logging.error(str(e))
        logging.info("Please create a .env file with CONCEPTSCAPE_GEMINI_API_KEY")
        raise

    result = extractor.process_chunks(preprocessed_data)
    all_concepts = result["concepts"]

    os.makedirs(settings.data_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    pdf_concepts = sum(1 for c in all_concepts if c.get("source_reference", {}).get("resource_type") == "pdf")
    ppt_concepts = sum(1 for c in all_concepts if c.get("source_reference", {}).get("resource_type") == "ppt")
    image_concepts = sum(1 for c in all_concepts if c.get("source_reference", {}).get("resource_type") == "image")

    logging.info("\n==================================================")
    logging.info("EXTRACTION COMPLETE")
    logging.info("==================================================")
    logging.info(f"Subject: {preprocessed_data.get('subject_id')}")
    logging.info("\nConcept mentions extracted by source type:")
    logging.info(f"  PDF: {pdf_concepts}")
    logging.info(f"  PPT: {ppt_concepts}")
    logging.info(f"  Images: {image_concepts}")
    logging.info(f"  Total: {len(all_concepts)}")
    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")

    failed_chunks = result.get("failed_chunks", [])
    if failed_chunks:
        raise RuntimeError(
            f"Concept extraction failed for {len(failed_chunks)} chunk(s); "
            "downstream stages were not run."
        )

if __name__ == "__main__":
    main()

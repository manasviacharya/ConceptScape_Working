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
    
    logging.info("Ingestion complete.")
    logging.info(f"Total resources: {len(result.resources)}")
    
    # Save output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        
    logging.info(f"Output saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

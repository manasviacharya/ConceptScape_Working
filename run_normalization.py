import json
import logging
import os
from dataclasses import asdict

from config import settings
from logging_setup import configure_logging
from normalization.normalizer import normalize


def main():
    configure_logging()

    INPUT_FILE = os.path.join(settings.data_dir, "extracted_concepts.json")
    OUTPUT_FILE = os.path.join(settings.data_dir, "normalized_concepts.json")

    if not os.path.exists(INPUT_FILE):
        logging.error(f"Extracted concepts not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    mentions = data.get("concepts", [])
    logging.info("ConceptScape Normalization starting...")
    logging.info(f"Input mentions: {len(mentions)}")

    concepts = normalize(mentions)

    merged = [c for c in concepts if c.occurrence_count > 1]
    logging.info(f"Canonical concepts: {len(concepts)} (from {len(mentions)} mentions)")
    logging.info(f"Concepts formed by merging >1 mention: {len(merged)}")

    logging.info("\nLargest merge groups:")
    for c in sorted(concepts, key=lambda x: -x.occurrence_count)[:10]:
        if c.occurrence_count > 1:
            logging.info(f"  {c.occurrence_count:3}x  {c.canonical_name[:44]:46} aliases={c.aliases}")

    os.makedirs(settings.data_dir, exist_ok=True)
    output = {
        "subject_id": data.get("subject_id", ""),
        "concepts": [asdict(c) for c in concepts],
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

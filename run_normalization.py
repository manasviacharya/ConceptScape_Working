import json
import logging
import os
from dataclasses import asdict

from config import settings
from logging_setup import configure_logging
from normalization.normalizer import normalize
from normalization.semantic_fusion import fuse
from quality.significance import filter_concepts


def main():
    configure_logging()

    INPUT_FILE = os.path.join(settings.data_dir, "extracted_concepts.json")
    OUTPUT_FILE = os.path.join(settings.data_dir, "normalized_concepts.json")

    if not os.path.exists(INPUT_FILE):
        logging.error(f"Extracted concepts not found: {INPUT_FILE}")
        raise FileNotFoundError(INPUT_FILE)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    mentions = data.get("concepts", [])
    failed_chunks = data.get("failed_chunks", [])
    if failed_chunks and not mentions:
        raise RuntimeError(
            f"Cannot normalize: extraction failed for {len(failed_chunks)} chunk(s) "
            "and produced no concept mentions."
        )
    logging.info("ConceptScape Normalization starting...")
    logging.info(f"Input mentions: {len(mentions)}")

    concepts = normalize(mentions)
    lexical_count = len(concepts)

    merge_log = []
    if settings.fusion_enabled:
        # Runs after lexical merging so it only has to bridge what string
        # matching genuinely cannot — far fewer pairs, and each surviving
        # concept already carries a consolidated definition to compare on.
        concepts, merge_log = fuse(concepts)

    merged = [c for c in concepts if c.occurrence_count > 1]
    logging.info(f"Canonical concepts: {len(concepts)} (from {len(mentions)} mentions)")
    if settings.fusion_enabled:
        logging.info(f"  lexical merge: {len(mentions)} -> {lexical_count}"
                     f" | semantic fusion: {lexical_count} -> {len(concepts)}")
    logging.info(f"Concepts formed by merging >1 mention: {len(merged)}")

    logging.info("\nLargest merge groups:")
    for c in sorted(concepts, key=lambda x: -x.occurrence_count)[:10]:
        if c.occurrence_count > 1:
            logging.info(f"  {c.occurrence_count:3}x  {c.canonical_name[:44]:46} aliases={c.aliases}")

    os.makedirs(settings.data_dir, exist_ok=True)
    output = {
        "subject_id": data.get("subject_id", ""),
        "concepts": [asdict(c) for c in concepts],
        "fusion_decisions": merge_log,
    }
    raw_concepts = output["concepts"]
    filtered_concepts, significance_audit = filter_concepts(raw_concepts) if settings.pedagogical_filter_enabled else (raw_concepts, [])
    with open(os.path.join(settings.data_dir, "normalized_concepts_raw.json"), "w", encoding="utf-8") as f:
        json.dump({"subject_id": data.get("subject_id", ""), "concepts": raw_concepts, "fusion_decisions": merge_log}, f, indent=2, ensure_ascii=False)
    output["concepts"] = filtered_concepts
    output["significance_audit"] = significance_audit
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logging.info(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

"""Run one explicit relationship through the real LLM-backed extractor."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from relationships.extractor import RelationshipExtractor


def main() -> None:
    chunks = {
        "chunks": [{
            "chunk_id": "controlled_c1",
            "resource_id": "controlled_doc",
            "filename": "controlled.txt",
            "text": "Gradient Descent requires a Learning Rate to converge.",
            "raw_page_text": "Gradient Descent requires a Learning Rate to converge.",
            "location_number": 1,
            "content_hash": "controlled",
        }]
    }
    concepts = {
        "concepts": [
            {"concept_id": "k1", "canonical_name": "Gradient Descent", "aliases": [], "chunk_ids": ["controlled_c1"]},
            {"concept_id": "k2", "canonical_name": "Learning Rate", "aliases": [], "chunk_ids": ["controlled_c1"]},
        ]
    }
    result = RelationshipExtractor().process(chunks, concepts)
    print(json.dumps({
        "count": len(result["relationships"]),
        "failed_chunks": result["failed_chunks"],
        "edges": [{
            "source": relationship.source_concept_id,
            "target": relationship.target_concept_id,
            "type": relationship.type,
            "evidence": relationship.evidence[0].text,
            "model": relationship.evidence[0].model_used,
        } for relationship in result["relationships"]],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

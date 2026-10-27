"""Real relationship-extractor to graph-store regression path.

The LLM boundary is stubbed, but the extractor validation, canonical ID
resolution, serialization-shaped model, graph upsert, and graph query are real.
"""

import json

from graph.memory_store import InMemoryGraphStore
from relationships.extractor import RelationshipExtractor


class StubLLM:
    def call(self, prompt, system_instruction, schema):
        return json.dumps({
            "relationships": [{
                "source": "Gradient Descent",
                "target": "Learning Rate",
                "type": "requires",
                "evidence": "Gradient Descent requires a Learning Rate to converge.",
                "confidence": 0.98,
            }]
        }), "stub-model"


def test_relationship_pipeline_persists_and_queries_explicit_edge():
    chunks = {
        "chunks": [{
            "chunk_id": "ch1",
            "resource_id": "doc1",
            "filename": "controlled.txt",
            "text": "Gradient Descent requires a Learning Rate to converge.",
            "raw_page_text": "Gradient Descent requires a Learning Rate to converge.",
            "location_number": 1,
            "content_hash": "h1",
        }]
    }
    concepts = {
        "concepts": [
            {
                "concept_id": "k1",
                "canonical_name": "Gradient Descent",
                "aliases": [],
                "chunk_ids": ["ch1"],
            },
            {
                "concept_id": "k2",
                "canonical_name": "Learning Rate",
                "aliases": [],
                "chunk_ids": ["ch1"],
            },
        ]
    }

    extractor = RelationshipExtractor()
    extractor.llm = StubLLM()
    result = extractor.process(chunks, concepts)

    assert len(result["relationships"]) == 1
    relationship = result["relationships"][0]
    assert relationship.source_concept_id == "k1"
    assert relationship.target_concept_id == "k2"
    assert relationship.type == "requires"
    assert relationship.evidence[0].chunk_id == "ch1"

    graph = InMemoryGraphStore()
    graph.connect()
    graph.upsert_concepts(concepts["concepts"])
    assert graph.upsert_relationships([
        {
            "relationship_id": relationship.relationship_id,
            "source_concept_id": relationship.source_concept_id,
            "target_concept_id": relationship.target_concept_id,
            "type": relationship.type,
            "resource_id": relationship.resource_id,
            "evidence": [vars(e) for e in relationship.evidence],
        }
    ]) == 1
    neighbors = graph.get_neighbors("k1")
    assert len(neighbors) == 1
    assert neighbors[0]["concept"]["concept_id"] == "k2"
    assert neighbors[0]["type"] == "requires"

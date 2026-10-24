"""Validate that generated ConceptScape artefacts form one coherent corpus."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    path = ROOT / relative
    if not path.exists():
        raise SystemExit(f"Missing artefact: {relative}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


manifest = load("demo_corpus.json")
missing_demo_documents = [
    name for name in manifest.get("documents", [])
    if not (ROOT / "documents" / name).is_file()
]
if missing_demo_documents:
    raise SystemExit(
        "Canonical demo corpus is incomplete: " + ", ".join(missing_demo_documents)
    )


ingestion = load("output/ingestion_result.json")
chunks = load("output/preprocessed_chunks.json")
mentions = load("data/extracted_concepts.json")
concepts = load("data/normalized_concepts.json")
relationships = load("data/relationships.json")
graph = load("data/graph_export.json")

resource_ids = {r["resource_id"] for r in ingestion.get("resources", [])}
chunk_ids = {c["chunk_id"] for c in chunks.get("chunks", [])}
concept_ids = {c["concept_id"] for c in concepts.get("concepts", [])}
graph_node_ids = {n["concept_id"] for n in graph.get("nodes", [])}

errors = []
if ingestion.get("subject_id") != chunks.get("subject_id"):
    errors.append("subject_id differs between ingestion and preprocessing")
if mentions.get("subject_id") != concepts.get("subject_id"):
    errors.append("subject_id differs between extraction and normalization")
if concepts.get("subject_id") != relationships.get("subject_id"):
    errors.append("subject_id differs between normalization and relationships")

for concept in concepts.get("concepts", []):
    missing = set(concept.get("chunk_ids", [])) - chunk_ids
    if missing:
        errors.append(f"concept {concept['concept_id']} references missing chunks: {sorted(missing)}")

for relationship in relationships.get("relationships", []):
    if relationship.get("source_concept_id") not in concept_ids:
        errors.append(f"relationship {relationship.get('relationship_id')} has missing source")
    if relationship.get("target_concept_id") not in concept_ids:
        errors.append(f"relationship {relationship.get('relationship_id')} has missing target")
    for evidence in relationship.get("evidence", []):
        if evidence.get("chunk_id") and evidence["chunk_id"] not in chunk_ids:
            errors.append(f"relationship evidence references missing chunk {evidence['chunk_id']}")

if graph_node_ids != concept_ids:
    errors.append("graph node IDs do not match normalized concept IDs")

if errors:
    print("Artifact validation FAILED")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("Artifact validation PASSED")
print(f"demo_corpus={manifest.get('name', 'unnamed')} documents={len(manifest.get('documents', []))}")
print(f"resources={len(resource_ids)} chunks={len(chunk_ids)} mentions={len(mentions.get('concepts', []))} "
      f"concepts={len(concept_ids)} relationships={len(relationships.get('relationships', []))} "
      f"graph_nodes={len(graph_node_ids)} graph_edges={len(graph.get('edges', []))}")

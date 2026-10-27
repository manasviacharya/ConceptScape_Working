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


def validate_artifact_data(
    manifest: dict,
    ingestion: dict,
    chunks: dict,
    mentions: dict,
    concepts: dict,
    relationships: dict,
    graph: dict,
    available_documents: set[str],
) -> list[str]:
    """Return all consistency errors without mutating generated artifacts.

    Keeping the checks pure makes the validator reusable from regression tests
    and makes stale-artifact/schema incompatibilities distinguishable from a
    pipeline execution failure.
    """
    errors = []
    missing_demo_documents = [
        name for name in manifest.get("documents", []) if name not in available_documents
    ]
    if missing_demo_documents:
        errors.append(
            "Canonical demo corpus is incomplete: " + ", ".join(missing_demo_documents)
        )

    chunk_ids = {c["chunk_id"] for c in chunks.get("chunks", [])}
    concept_ids = {c["concept_id"] for c in concepts.get("concepts", [])}
    graph_node_ids = {n["concept_id"] for n in graph.get("nodes", [])}

    if ingestion.get("subject_id") != chunks.get("subject_id"):
        errors.append("subject_id differs between ingestion and preprocessing")
    if mentions.get("subject_id") != concepts.get("subject_id"):
        errors.append("subject_id differs between extraction and normalization")
    if concepts.get("subject_id") != relationships.get("subject_id"):
        errors.append("subject_id differs between normalization and relationships")

    skipped = mentions.get("skipped_chunks", [])
    if not isinstance(skipped, list):
        errors.append("extraction skipped_chunks must be a list")
        skipped = []
    skipped_ids = {item.get("chunk_id") for item in skipped if isinstance(item, dict)}
    failed_ids = set(mentions.get("failed_chunks", []))
    processed_ids = set(mentions.get("processed_chunks", {}))
    if None in skipped_ids:
        errors.append("extraction skipped_chunks contains an entry without chunk_id")
        skipped_ids.discard(None)
    if skipped_ids & failed_ids:
        errors.append("extraction chunk cannot be both skipped and failed")
    if skipped_ids & processed_ids:
        errors.append("extraction chunk cannot be both skipped and processed")
    if not skipped_ids <= chunk_ids:
        errors.append("extraction skipped_chunks references missing chunks")
    for item in skipped:
        if isinstance(item, dict) and item.get("chunk_id") in skipped_ids:
            for field in ("filename", "reason", "content_hash"):
                if not item.get(field):
                    errors.append(
                        f"skipped chunk {item['chunk_id']} missing {field}"
                    )

    accounted = processed_ids | failed_ids | skipped_ids
    if accounted != chunk_ids:
        missing = chunk_ids - accounted
        extra = accounted - chunk_ids
        if missing:
            errors.append(f"extraction does not account for chunks: {sorted(missing)}")
        if extra:
            errors.append(f"extraction accounts for unknown chunks: {sorted(extra)}")

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
    return errors


def main() -> int:
    manifest = load("demo_corpus.json")
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
    errors = validate_artifact_data(
        manifest,
        ingestion,
        chunks,
        mentions,
        concepts,
        relationships,
        graph,
        {path.name for path in (ROOT / "documents").iterdir() if path.is_file()},
    )

    if errors:
        print("Artifact validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Artifact validation PASSED")
    print(f"demo_corpus={manifest.get('name', 'unnamed')} documents={len(manifest.get('documents', []))}")
    print(f"resources={len(resource_ids)} chunks={len(chunk_ids)} mentions={len(mentions.get('concepts', []))} "
          f"concepts={len(concept_ids)} relationships={len(relationships.get('relationships', []))} "
          f"graph_nodes={len(graph_node_ids)} graph_edges={len(graph.get('edges', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

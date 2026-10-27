import json
import logging
import os

from config import settings
from logging_setup import configure_logging
from graph.memory_store import InMemoryGraphStore
from graph.neo4j_store import Neo4jGraphStore


def main():
    configure_logging()

    CONCEPTS_FILE = os.path.join(settings.data_dir, "normalized_concepts.json")
    RELS_FILE = os.path.join(settings.data_dir, "relationships.json")

    for path in (CONCEPTS_FILE, RELS_FILE):
        if not os.path.exists(path):
            logging.error(f"Required input not found: {path}")
            raise FileNotFoundError(path)

    with open(CONCEPTS_FILE, "r", encoding="utf-8") as f:
        concepts = json.load(f).get("concepts", [])
    with open(RELS_FILE, "r", encoding="utf-8") as f:
        relationships = json.load(f).get("relationships", [])

    logging.info("ConceptScape Graph Build starting...")
    logging.info(f"Concepts: {len(concepts)} | Relationships: {len(relationships)}")

    # Neo4j is preferred, but Bolt (7687) is blocked on many managed networks and
    # has no HTTPS fallback. Rather than leave the app with no graph at all, fall
    # back to the in-memory store — the export and every query the UI and
    # retriever use go through BaseGraphStore, so nothing downstream changes.
    store = Neo4jGraphStore()
    try:
        store.connect()
    except Exception as e:
        logging.warning(f"Neo4j unavailable ({str(e)[:120]})")
        if not settings.graph_allow_memory_fallback:
            logging.error("Falling back is disabled (graph_allow_memory_fallback=False). Aborting.")
            return
        logging.warning("Falling back to the in-memory graph store")
        store = InMemoryGraphStore()
        store.connect()

    try:
        store.init_schema()
        store.clear()
        n = store.upsert_concepts(concepts)
        logging.info(f"Loaded {n} concept nodes")
        m = store.upsert_relationships(relationships)
        logging.info(f"Loaded {m} relationships")

        s = store.stats()
        logging.info("\n" + "=" * 50)
        logging.info("GRAPH BUILD COMPLETE")
        logging.info("=" * 50)
        logging.info(f"Concepts        : {s['concepts']}")
        logging.info(f"Relationships   : {s['relationships']}")
        logging.info(f"Isolated (no edges): {s['isolated_concepts']}")
        logging.info("\nBy relationship type:")
        for t, c in s["by_type"].items():
            logging.info(f"  {c:4}  {t}")

        logging.info("\nMost connected concepts:")
        for row in store.most_connected(10):
            logging.info(f"  degree={row['degree']:3}  {row['name']}")

        export_path = os.path.join(settings.data_dir, "graph_export.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(store.export_graph(), f, indent=2, ensure_ascii=False)
        logging.info(f"\nGraph export saved to: {export_path}")
    finally:
        store.close()


if __name__ == "__main__":
    main()

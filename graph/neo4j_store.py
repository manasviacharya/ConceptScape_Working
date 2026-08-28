import logging
import os
from typing import Any, Dict, List, Optional

from config import settings
from graph.graph_store import BaseGraphStore

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


# Relationship type is stored as a PROPERTY rather than as the edge label.
# Neo4j cannot parameterise labels, so a label-per-type would mean building
# Cypher by string concatenation, and querying "all relationships" would need
# every type enumerated. As a property the controlled vocabulary stays
# queryable as data: MATCH ()-[r:RELATES_TO {type:'requires'}]->().
_EDGE = "RELATES_TO"


def _ensure_ca_bundle() -> None:
    """
    Point Python's SSL layer at certifi's CA bundle if it has none.

    On macOS python.org installs, `Install Certificates.command` is often never
    run, leaving ssl.get_default_verify_paths().cafile as None. Aura requires
    TLS (neo4j+s://), so the handshake then fails with an SSLCertVerificationError
    that surfaces confusingly as "Unable to retrieve routing information".
    """
    import ssl
    if ssl.get_default_verify_paths().cafile:
        return
    try:
        import certifi
    except ImportError:
        return
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    logging.info("No system CA bundle found — using certifi for TLS verification")


class Neo4jGraphStore(BaseGraphStore):
    def __init__(self, uri: str = "", user: str = "", password: str = "", database: str = ""):
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database
        self._driver = None

    # ── lifecycle ────────────────────────────────────────────────────────

    def connect(self) -> None:
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j driver not installed. Run: pip install neo4j")
        if not self.uri or not self.password:
            raise ValueError(
                "Neo4j credentials missing. Set CONCEPTSCAPE_NEO4J_URI, "
                "CONCEPTSCAPE_NEO4J_USER and CONCEPTSCAPE_NEO4J_PASSWORD in .env"
            )
        if self._driver is None:
            _ensure_ca_bundle()
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._driver.verify_connectivity()
            logging.info(f"Connected to Neo4j at {self.uri} (database={self.database})")

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    def _run(self, cypher: str, **params):
        with self._driver.session(database=self.database) as session:
            return list(session.run(cypher, **params))

    # ── schema / loading ─────────────────────────────────────────────────

    def init_schema(self) -> None:
        self._run(
            "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS "
            "FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE"
        )
        self._run(
            "CREATE INDEX concept_name_idx IF NOT EXISTS "
            "FOR (c:Concept) ON (c.canonical_name)"
        )
        logging.info("Schema ready (constraint on concept_id, index on canonical_name)")

    def clear(self) -> None:
        self._run(f"MATCH (c:Concept) DETACH DELETE c")
        logging.info("Cleared existing graph")

    def upsert_concepts(self, concepts: List[Dict[str, Any]]) -> int:
        # MERGE on concept_id makes reloading idempotent — rebuilding the graph
        # after a re-extraction updates nodes instead of duplicating them.
        self._run(
            """
            UNWIND $rows AS row
            MERGE (c:Concept {concept_id: row.concept_id})
            SET c.canonical_name  = row.canonical_name,
                c.definition      = row.definition,
                c.aliases         = row.aliases,
                c.keywords        = row.keywords,
                c.chunk_ids       = row.chunk_ids,
                c.filenames       = row.filenames,
                c.page_numbers    = row.page_numbers,
                c.evidence        = row.evidence,
                c.occurrence_count= row.occurrence_count,
                c.mean_confidence = row.mean_confidence,
                c.models_used     = row.models_used,
                c.resource_ids    = row.resource_ids
            """,
            rows=concepts,
        )
        return len(concepts)

    def upsert_relationships(self, relationships: List[Dict[str, Any]]) -> int:
        # Neo4j properties must be primitives or lists of primitives, so the
        # evidence records are flattened into parallel lists. Index i of each
        # list belongs to the same evidence record.
        rows = []
        for r in relationships:
            ev = r.get("evidence") or []
            rows.append({
                "relationship_id": r["relationship_id"],
                "source_concept_id": r["source_concept_id"],
                "target_concept_id": r["target_concept_id"],
                "type": r["type"],
                "resource_id": r.get("resource_id", ""),
                "occurrence_count": r.get("occurrence_count", len(ev)),
                "mean_confidence": r.get("mean_confidence", 0.0),
                "chunk_ids": r.get("chunk_ids", []),
                "evidence_texts": [e.get("text", "") for e in ev],
                "evidence_filenames": [e.get("filename", "") for e in ev],
                "evidence_locations": [e.get("location_number", 0) for e in ev],
                "evidence_scopes": [e.get("scope", "") for e in ev],
                "models_used": sorted({e.get("model_used", "") for e in ev if e.get("model_used")}),
            })

        self._run(
            f"""
            UNWIND $rows AS row
            MATCH (a:Concept {{concept_id: row.source_concept_id}})
            MATCH (b:Concept {{concept_id: row.target_concept_id}})
            MERGE (a)-[r:{_EDGE} {{relationship_id: row.relationship_id}}]->(b)
            SET r.type               = row.type,
                r.resource_id        = row.resource_id,
                r.occurrence_count   = row.occurrence_count,
                r.mean_confidence    = row.mean_confidence,
                r.chunk_ids          = row.chunk_ids,
                r.evidence_texts     = row.evidence_texts,
                r.evidence_filenames = row.evidence_filenames,
                r.evidence_locations = row.evidence_locations,
                r.evidence_scopes    = row.evidence_scopes,
                r.models_used        = row.models_used
            """,
            rows=rows,
        )
        return len(rows)

    # ── queries ──────────────────────────────────────────────────────────

    def get_concept(self, name: str) -> Optional[Dict[str, Any]]:
        rows = self._run(
            """
            MATCH (c:Concept)
            WHERE toLower(c.canonical_name) = toLower($name)
               OR any(a IN c.aliases WHERE toLower(a) = toLower($name))
            RETURN c LIMIT 1
            """,
            name=name,
        )
        return dict(rows[0]["c"]) if rows else None

    def get_neighbors(self, concept_id: str) -> List[Dict[str, Any]]:
        rows = self._run(
            f"""
            MATCH (c:Concept {{concept_id: $cid}})-[r:{_EDGE}]-(n:Concept)
            RETURN n, r.type AS type, r.evidence_texts AS evidence,
                   startNode(r).concept_id = $cid AS outgoing
            """,
            cid=concept_id,
        )
        return [
            {
                "concept": dict(r["n"]),
                "type": r["type"],
                "evidence": r["evidence"],
                "direction": "outgoing" if r["outgoing"] else "incoming",
            }
            for r in rows
        ]

    def get_subgraph(self, concept_id: str, hops: int = 2) -> Dict[str, Any]:
        # hops is interpolated because Cypher does not allow a parameter inside
        # a variable-length pattern. Coerced to int first so it cannot inject.
        hops = max(1, int(hops))
        rows = self._run(
            f"""
            MATCH path = (c:Concept {{concept_id: $cid}})-[:{_EDGE}*1..{hops}]-(n:Concept)
            UNWIND relationships(path) AS rel
            RETURN DISTINCT startNode(rel) AS a, endNode(rel) AS b, rel
            """,
            cid=concept_id,
        )
        nodes, edges = {}, []
        for r in rows:
            for key in ("a", "b"):
                n = dict(r[key])
                nodes[n["concept_id"]] = n
            rel = dict(r["rel"])
            rel["source_concept_id"] = r["a"]["concept_id"]
            rel["target_concept_id"] = r["b"]["concept_id"]
            edges.append(rel)
        return {"nodes": list(nodes.values()), "edges": edges}

    def shortest_path(self, source_id: str, target_id: str) -> List[Dict[str, Any]]:
        rows = self._run(
            f"""
            MATCH (a:Concept {{concept_id: $src}}), (b:Concept {{concept_id: $tgt}}),
                  path = shortestPath((a)-[:{_EDGE}*..8]-(b))
            RETURN [n IN nodes(path) | n.canonical_name] AS names,
                   [r IN relationships(path) | r.type] AS types
            """,
            src=source_id, tgt=target_id,
        )
        if not rows:
            return []
        return [{"names": rows[0]["names"], "types": rows[0]["types"]}]

    def concepts_by_document(self, filename: str) -> List[Dict[str, Any]]:
        rows = self._run(
            "MATCH (c:Concept) WHERE $fn IN c.filenames RETURN c ORDER BY c.canonical_name",
            fn=filename,
        )
        return [dict(r["c"]) for r in rows]

    def most_connected(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self._run(
            f"""
            MATCH (c:Concept)
            OPTIONAL MATCH (c)-[r:{_EDGE}]-()
            WITH c, count(r) AS degree
            RETURN c.canonical_name AS name, c.concept_id AS concept_id,
                   degree, c.occurrence_count AS occurrences
            ORDER BY degree DESC, occurrences DESC LIMIT $limit
            """,
            limit=int(limit),
        )
        return [dict(r) for r in rows]

    def export_graph(self) -> Dict[str, Any]:
        nodes = [dict(r["c"]) for r in self._run("MATCH (c:Concept) RETURN c")]
        edges = []
        for r in self._run(
            f"MATCH (a:Concept)-[r:{_EDGE}]->(b:Concept) "
            "RETURN a.concept_id AS s, b.concept_id AS t, r"
        ):
            e = dict(r["r"])
            e["source_concept_id"] = r["s"]
            e["target_concept_id"] = r["t"]
            edges.append(e)
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> Dict[str, Any]:
        n = self._run("MATCH (c:Concept) RETURN count(c) AS n")[0]["n"]
        e = self._run(f"MATCH ()-[r:{_EDGE}]->() RETURN count(r) AS n")[0]["n"]
        types = {
            r["type"]: r["n"]
            for r in self._run(
                f"MATCH ()-[r:{_EDGE}]->() RETURN r.type AS type, count(*) AS n ORDER BY n DESC"
            )
        }
        isolated = self._run(
            f"MATCH (c:Concept) WHERE NOT (c)-[:{_EDGE}]-() RETURN count(c) AS n"
        )[0]["n"]
        return {"concepts": n, "relationships": e, "by_type": types, "isolated_concepts": isolated}

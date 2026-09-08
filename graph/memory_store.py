import logging
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from graph.graph_store import BaseGraphStore

_EDGE_KEY = "RELATES_TO"


class InMemoryGraphStore(BaseGraphStore):
    """
    Graph store held in plain Python dictionaries.

    Exists because Neo4j is reachable only over Bolt on port 7687, which managed
    networks (campus, corporate, public wifi) routinely block — and unlike HTTPS
    services there is no port-443 fallback. A demo that cannot draw its own graph
    because of a firewall is not an acceptable failure mode.

    At this corpus size the tradeoff is negligible: eighty concepts fit in memory
    and every query below answers in microseconds. What is lost is persistence
    and Cypher, neither of which the application depends on — it reads the graph
    through this interface, exactly so the backend can change.
    """

    def __init__(self):
        self._concepts: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
        self._adj: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # ── lifecycle ────────────────────────────────────────────────────────

    def connect(self) -> None:
        logging.info("Using in-memory graph store (no database required)")

    def close(self) -> None:
        pass

    def init_schema(self) -> None:
        pass  # nothing to create; uniqueness is enforced by the concept_id dict

    def clear(self) -> None:
        self._concepts.clear()
        self._edges.clear()
        self._adj.clear()

    # ── loading ──────────────────────────────────────────────────────────

    def upsert_concepts(self, concepts: List[Dict[str, Any]]) -> int:
        for c in concepts:
            self._concepts[c["concept_id"]] = dict(c)
        return len(concepts)

    def upsert_relationships(self, relationships: List[Dict[str, Any]]) -> int:
        added = 0
        for r in relationships:
            src, tgt = r.get("source_concept_id"), r.get("target_concept_id")
            # Mirrors the Cypher loader, which MATCHes both endpoints: an edge
            # to a concept that does not exist is silently skipped rather than
            # creating a dangling reference.
            if src not in self._concepts or tgt not in self._concepts:
                continue
            ev = r.get("evidence") or []
            edge = {
                "relationship_id": r["relationship_id"],
                "source_concept_id": src,
                "target_concept_id": tgt,
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
            }
            self._edges.append(edge)
            self._adj[src].append({**edge, "direction": "outgoing", "other": tgt})
            self._adj[tgt].append({**edge, "direction": "incoming", "other": src})
            added += 1
        return added

    # ── queries ──────────────────────────────────────────────────────────

    def get_concept(self, name: str) -> Optional[Dict[str, Any]]:
        needle = (name or "").casefold()
        for c in self._concepts.values():
            if c.get("canonical_name", "").casefold() == needle:
                return c
        for c in self._concepts.values():
            if any(a.casefold() == needle for a in c.get("aliases", [])):
                return c
        return None

    def get_neighbors(self, concept_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "concept": self._concepts[e["other"]],
                "type": e["type"],
                "evidence": e["evidence_texts"],
                "direction": e["direction"],
            }
            for e in self._adj.get(concept_id, [])
            if e["other"] in self._concepts
        ]

    def get_subgraph(self, concept_id: str, hops: int = 2) -> Dict[str, Any]:
        if concept_id not in self._concepts:
            return {"nodes": [], "edges": []}
        seen = {concept_id}
        frontier = [concept_id]
        for _ in range(max(1, int(hops))):
            nxt = []
            for cid in frontier:
                for e in self._adj.get(cid, []):
                    if e["other"] not in seen:
                        seen.add(e["other"])
                        nxt.append(e["other"])
            frontier = nxt
        edges = [
            e for e in self._edges
            if e["source_concept_id"] in seen and e["target_concept_id"] in seen
        ]
        return {"nodes": [self._concepts[i] for i in seen], "edges": edges}

    def shortest_path(self, source_id: str, target_id: str) -> List[Dict[str, Any]]:
        if source_id not in self._concepts or target_id not in self._concepts:
            return []
        # Breadth-first search: edges are unweighted, so BFS gives the shortest
        # path and stops as soon as the target is reached.
        prev: Dict[str, tuple] = {source_id: (None, None)}
        queue = deque([source_id])
        while queue:
            cur = queue.popleft()
            if cur == target_id:
                break
            for e in self._adj.get(cur, []):
                if e["other"] not in prev:
                    prev[e["other"]] = (cur, e["type"])
                    queue.append(e["other"])
        if target_id not in prev:
            return []

        names, types, node = [], [], target_id
        while node is not None:
            names.append(self._concepts[node]["canonical_name"])
            parent, rtype = prev[node]
            if rtype:
                types.append(rtype)
            node = parent
        return [{"names": list(reversed(names)), "types": list(reversed(types))}]

    def concepts_by_document(self, filename: str) -> List[Dict[str, Any]]:
        return sorted(
            (c for c in self._concepts.values() if filename in c.get("filenames", [])),
            key=lambda c: c.get("canonical_name", ""),
        )

    def most_connected(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = [
            {
                "name": c.get("canonical_name", ""),
                "concept_id": cid,
                "degree": len(self._adj.get(cid, [])),
                "occurrences": c.get("occurrence_count", 0),
            }
            for cid, c in self._concepts.items()
        ]
        rows.sort(key=lambda r: (-r["degree"], -r["occurrences"]))
        return rows[: int(limit)]

    def export_graph(self) -> Dict[str, Any]:
        return {"nodes": list(self._concepts.values()), "edges": list(self._edges)}

    def stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = defaultdict(int)
        for e in self._edges:
            by_type[e["type"]] += 1
        isolated = sum(1 for cid in self._concepts if not self._adj.get(cid))
        return {
            "concepts": len(self._concepts),
            "relationships": len(self._edges),
            "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
            "isolated_concepts": isolated,
        }

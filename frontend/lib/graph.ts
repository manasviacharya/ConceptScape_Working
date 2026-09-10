import dagre from "dagre";
import type { Edge, Node } from "reactflow";

// These mirror what graph_store's export actually emits. A concept spans
// several documents after cross-document merging, hence resource_ids/filenames
// being lists rather than single values.
export type ConceptNode = {
  concept_id: string;
  canonical_name: string;
  definition: string;
  aliases: string[];
  keywords: string[];
  chunk_ids: string[];
  filenames: string[];
  page_numbers: number[];
  // Typed positions. page_numbers alone cannot say whether 57 means page 57 or
  // 57 seconds into a video, so anything user-facing reads this instead.
  locations?: { type: string; number: number; filename: string }[];
  evidence: string[];
  occurrence_count: number;
  mean_confidence: number;
  models_used: string[];
  resource_ids: string[];
};

// One edge can be supported by several evidence records, stored as parallel
// arrays because Neo4j properties cannot nest. Index i of each array belongs
// to the same record.
export type ConceptEdge = {
  relationship_id: string;
  source_concept_id: string;
  target_concept_id: string;
  type: string;
  resource_id: string;
  occurrence_count: number;
  mean_confidence: number;
  chunk_ids: string[];
  evidence_texts: string[];
  evidence_filenames: string[];
  evidence_locations: number[];
  evidence_scopes: string[];
  models_used: string[];
};

export type GraphExport = { nodes: ConceptNode[]; edges: ConceptEdge[] };

// One colour per relationship type. The controlled vocabulary is small and
// fixed, so the legend stays readable and edge meaning is visible at a glance.
export const TYPE_COLORS: Record<string, string> = {
  depends_on: "#e07a5f",
  requires: "#e07a5f",
  part_of: "#3d8dae",
  example_of: "#6a9955",
  used_for: "#b58900",
  produces: "#8a63d2",
  causes: "#c2255c",
  related_to: "#8a8a8a",
  prerequisite_of: "#d1495b",
};

const NODE_W = 210;
const NODE_H = 62;

export function neighboursOf(id: string, edges: ConceptEdge[]): Set<string> {
  const out = new Set<string>();
  for (const e of edges) {
    if (e.source_concept_id === id) out.add(e.target_concept_id);
    if (e.target_concept_id === id) out.add(e.source_concept_id);
  }
  return out;
}

/**
 * Concepts within `hops` edges of a focus concept, plus the edges among them.
 *
 * Showing all 76 concepts at once produces an unreadable hairball; a focused
 * neighbourhood is what makes the graph legible as a teaching artefact — you
 * read one concept and how it connects, then walk outward.
 */
export function subgraph(focusId: string, nodes: ConceptNode[], edges: ConceptEdge[], hops: number) {
  const keep = new Set([focusId]);
  const depth = new Map<string, number>([[focusId, 0]]);
  let frontier = [focusId];

  for (let h = 1; h <= hops; h++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const n of neighboursOf(id, edges)) {
        if (!keep.has(n)) {
          keep.add(n);
          depth.set(n, h);
          next.push(n);
        }
      }
    }
    frontier = next;
  }

  return {
    nodes: nodes.filter((n) => keep.has(n.concept_id)),
    edges: edges.filter((e) => keep.has(e.source_concept_id) && keep.has(e.target_concept_id)),
    depth,
  };
}

/**
 * Rings by hop distance: focus in the centre, direct neighbours around it,
 * second-hop concepts on an outer ring.
 *
 * Chosen over dagre for focus mode because the question being answered is
 * "what is this connected to", and concentric distance reads that directly.
 */
export function radialLayout(
  focusId: string,
  nodes: ConceptNode[],
  edges: ConceptEdge[],
  depth: Map<string, number>
) {
  const degree = new Map<string, number>();
  for (const e of edges) {
    degree.set(e.source_concept_id, (degree.get(e.source_concept_id) ?? 0) + 1);
    degree.set(e.target_concept_id, (degree.get(e.target_concept_id) ?? 0) + 1);
  }

  const rings = new Map<number, ConceptNode[]>();
  for (const n of nodes) {
    const d = depth.get(n.concept_id) ?? 1;
    if (!rings.has(d)) rings.set(d, []);
    rings.get(d)!.push(n);
  }

  const positioned: Node[] = [];
  for (const [d, ring] of Array.from(rings.entries()).sort((a, b) => a[0] - b[0])) {
    if (d === 0) {
      positioned.push(makeNode(ring[0], 0, 0, degree, depth));
      continue;
    }
    // Radius grows with both hop distance and ring population so a busy ring
    // does not overlap itself.
    const radius = d * 300 + Math.max(0, ring.length - 6) * 26;
    ring.forEach((n, i) => {
      const angle = (i / ring.length) * 2 * Math.PI - Math.PI / 2;
      positioned.push(
        makeNode(n, Math.cos(angle) * radius, Math.sin(angle) * radius * 0.78, degree, depth)
      );
    });
  }

  return { nodes: positioned, edges: styleEdges(edges) };
}

function makeNode(
  concept: ConceptNode,
  x: number,
  y: number,
  degree: Map<string, number>,
  depth: Map<string, number>
): Node {
  return {
    id: concept.concept_id,
    position: { x: x - NODE_W / 2, y: y - NODE_H / 2 },
    data: {
      concept,
      degree: degree.get(concept.concept_id) ?? 0,
      depth: depth.get(concept.concept_id) ?? 0,
    },
    type: "concept",
  };
}

function styleEdges(edges: ConceptEdge[]): Edge[] {
  return edges.map((e) => ({
    id: e.relationship_id,
    source: e.source_concept_id,
    target: e.target_concept_id,
    label: e.type,
    data: e,
    type: "default",
    markerEnd: { type: "arrowclosed" as any, color: TYPE_COLORS[e.type] ?? "#999", width: 16, height: 16 },
    style: { stroke: TYPE_COLORS[e.type] ?? "#999", strokeWidth: 1.8 },
    labelStyle: { fontSize: 11, fill: "#4a4a46", fontWeight: 500 },
    labelBgStyle: { fill: "#fff", fillOpacity: 0.92 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 3,
  }));
}

/**
 * Dagre layout over the connected component(s), with isolated concepts packed
 * into a grid beneath. Dagre alone would strand ~half the nodes in one long
 * row — with 48 of 99 concepts unconnected, that row dominates the canvas and
 * hides the actual graph.
 */
export function layout(nodes: ConceptNode[], edges: ConceptEdge[]) {
  const degree = new Map<string, number>();
  for (const e of edges) {
    degree.set(e.source_concept_id, (degree.get(e.source_concept_id) ?? 0) + 1);
    degree.set(e.target_concept_id, (degree.get(e.target_concept_id) ?? 0) + 1);
  }

  const connected = nodes.filter((n) => (degree.get(n.concept_id) ?? 0) > 0);
  const isolated = nodes.filter((n) => (degree.get(n.concept_id) ?? 0) === 0);

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 55, ranksep: 90 });

  for (const n of connected) g.setNode(n.concept_id, { width: NODE_W, height: NODE_H });
  for (const e of edges) g.setEdge(e.source_concept_id, e.target_concept_id);
  dagre.layout(g);

  let maxY = 0;
  const positioned: Node[] = connected.map((n) => {
    const p = g.node(n.concept_id);
    maxY = Math.max(maxY, p.y);
    return {
      id: n.concept_id,
      position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 },
      data: { concept: n, degree: degree.get(n.concept_id) ?? 0 },
      type: "concept",
    };
  });

  const PER_ROW = 6;
  isolated.forEach((n, i) => {
    positioned.push({
      id: n.concept_id,
      position: {
        x: (i % PER_ROW) * (NODE_W + 30),
        y: maxY + 180 + Math.floor(i / PER_ROW) * (NODE_H + 26),
      },
      data: { concept: n, degree: 0 },
      type: "concept",
    });
  });

  return {
    nodes: positioned,
    edges: styleEdges(edges),
    connectedCount: connected.length,
    isolatedCount: isolated.length,
  };
}

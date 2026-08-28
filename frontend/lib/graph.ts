import dagre from "dagre";
import type { Edge, Node } from "reactflow";

export type ConceptNode = {
  concept_id: string;
  canonical_name: string;
  definition: string;
  aliases: string[];
  keywords: string[];
  chunk_ids: string[];
  filenames: string[];
  page_numbers: number[];
  evidence: string[];
  occurrence_count: number;
  mean_confidence: number;
  models_used: string[];
  resource_id: string;
};

export type ConceptEdge = {
  relationship_id: string;
  source_concept_id: string;
  target_concept_id: string;
  type: string;
  evidence: string;
  confidence: number;
  chunk_id: string;
  filename: string;
  location_number: number;
  model_used: string;
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

const NODE_W = 190;
const NODE_H = 52;

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

  const flowEdges: Edge[] = edges.map((e) => ({
    id: e.relationship_id,
    source: e.source_concept_id,
    target: e.target_concept_id,
    label: e.type,
    data: e,
    animated: false,
    style: { stroke: TYPE_COLORS[e.type] ?? "#999", strokeWidth: 1.6 },
    labelStyle: { fontSize: 10, fill: "#555" },
    labelBgStyle: { fill: "#fff", fillOpacity: 0.85 },
  }));

  return { nodes: positioned, edges: flowEdges, connectedCount: connected.length, isolatedCount: isolated.length };
}

"use client";

import { useEffect, useMemo, useState } from "react";
import ReactFlow, { Background, Controls, type Edge, type Node } from "reactflow";
import ConceptList from "./ConceptList";
import ConceptNode from "./ConceptNode";
import DetailPanel from "./DetailPanel";
import {
  TYPE_COLORS,
  layout,
  radialLayout,
  subgraph,
  type ConceptEdge,
  type ConceptNode as Concept,
  type GraphExport,
} from "@/lib/graph";

const nodeTypes = { concept: ConceptNode };

export default function Page() {
  const [graph, setGraph] = useState<GraphExport | null>(null);
  const [error, setError] = useState("");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [hops, setHops] = useState(1);
  const [overview, setOverview] = useState(false);

  useEffect(() => {
    fetch("/data/graph_export.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((g: GraphExport) => {
        setGraph(g);
        // Open on the most connected concept rather than an empty canvas, so the
        // first thing seen is a readable, representative piece of the graph.
        const degree = new Map<string, number>();
        for (const e of g.edges) {
          degree.set(e.source_concept_id, (degree.get(e.source_concept_id) ?? 0) + 1);
          degree.set(e.target_concept_id, (degree.get(e.target_concept_id) ?? 0) + 1);
        }
        const hub = [...g.nodes].sort(
          (a, b) => (degree.get(b.concept_id) ?? 0) - (degree.get(a.concept_id) ?? 0)
        )[0];
        if (hub) setFocusId(hub.concept_id);
      })
      .catch((e) =>
        setError(
          `Could not load the graph (${e.message}). Run "python run_build_graph.py", then "npm run sync".`
        )
      );
  }, []);

  const conceptsById = useMemo(() => {
    const m: Record<string, Concept> = {};
    for (const n of graph?.nodes ?? []) m[n.concept_id] = n;
    return m;
  }, [graph]);

  const view = useMemo(() => {
    if (!graph) return null;
    if (overview || !focusId) {
      const connected = graph.nodes.filter((n) =>
        graph.edges.some(
          (e) => e.source_concept_id === n.concept_id || e.target_concept_id === n.concept_id
        )
      );
      const ids = new Set(connected.map((n) => n.concept_id));
      const edges = graph.edges.filter(
        (e) => ids.has(e.source_concept_id) && ids.has(e.target_concept_id)
      );
      return { ...layout(connected, edges), shown: connected.length };
    }
    const sub = subgraph(focusId, graph.nodes, graph.edges, hops);
    return { ...radialLayout(focusId, sub.nodes, sub.edges, sub.depth), shown: sub.nodes.length };
  }, [graph, focusId, hops, overview]);

  const nodes: Node[] = useMemo(
    () =>
      (view?.nodes ?? []).map((n) => ({
        ...n,
        data: { ...n.data, selected: n.id === focusId },
      })),
    [view, focusId]
  );

  const edges: Edge[] = view?.edges ?? [];

  if (error) return <div className="fullmsg">{error}</div>;
  if (!graph || !view) return <div className="fullmsg">Loading graph…</div>;

  const focus = focusId ? conceptsById[focusId] ?? null : null;
  const usedTypes = Array.from(new Set(graph.edges.map((e) => e.type))).sort();

  return (
    <div className="layout">
      <ConceptList
        concepts={graph.nodes}
        edges={graph.edges as ConceptEdge[]}
        focusId={focusId}
        search={search}
        onSearch={setSearch}
        onFocus={(id) => {
          setFocusId(id);
          setOverview(false);
        }}
      />

      <div className="canvas">
        <div className="topbar">
          <span className="title">ConceptScape</span>
          <span className="stats">
            {overview
              ? `overview · ${view.shown} connected concepts`
              : `${focus?.canonical_name ?? ""} · ${view.shown} concepts within ${hops} hop${hops === 1 ? "" : "s"}`}
          </span>

          <div className="controls">
            {!overview && (
              <div className="segmented">
                {[1, 2].map((h) => (
                  <button
                    key={h}
                    className={hops === h ? "seg active" : "seg"}
                    onClick={() => setHops(h)}
                  >
                    {h} hop{h === 1 ? "" : "s"}
                  </button>
                ))}
              </div>
            )}
            <button className="seg" onClick={() => setOverview((v) => !v)}>
              {overview ? "← focus view" : "whole graph"}
            </button>
          </div>
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => {
            setFocusId(node.id);
            setOverview(false);
          }}
          fitView
          fitViewOptions={{ padding: 0.22 }}
          minZoom={0.08}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} color="#e6e5e0" />
          <Controls showInteractive={false} />
        </ReactFlow>

        <div className="legend">
          {usedTypes.map((t) => (
            <div className="legend-item" key={t}>
              <span className="swatch" style={{ background: TYPE_COLORS[t] ?? "#999" }} />
              {t}
            </div>
          ))}
        </div>

        {!overview && view.shown === 1 && (
          <div className="hint">
            This concept has no relationships — the source material never explicitly
            stated one. Edges are only created where the text supports them.
          </div>
        )}
      </div>

      <DetailPanel
        concept={focus}
        edges={graph.edges as ConceptEdge[]}
        conceptsById={conceptsById}
        onSelect={(id) => {
          setFocusId(id);
          setOverview(false);
        }}
        onClose={() => setFocusId(null)}
      />
    </div>
  );
}

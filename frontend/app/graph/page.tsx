"use client";

import { useEffect, useMemo, useState } from "react";
import ReactFlow, { Background, Controls, type Edge, type Node, BackgroundVariant } from "reactflow";
import { motion, AnimatePresence } from "framer-motion";
import ConceptList from "../ConceptList";
import ConceptNode from "../ConceptNode";
import DetailPanel from "../DetailPanel";
import { Navbar } from "@/components/Navbar";
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

export default function GraphPage() {
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
          `Could not load the graph (${e.message}). Upload documents and run the pipeline first.`
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

  if (error) return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Navbar />
      <div className="fullmsg" style={{ paddingTop: 120 }}>{error}</div>
    </div>
  );
  if (!graph || !view) return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Navbar />
      <div className="fullmsg" style={{ paddingTop: 120 }}>Loading graph…</div>
    </div>
  );

  const focus = focusId ? conceptsById[focusId] ?? null : null;
  const usedTypes = Array.from(new Set(graph.edges.map((e) => e.type))).sort();

  return (
    <div className="layout" style={{ paddingTop: 0 }}>
      <Navbar />

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
        <div className="controls-bar">
          <span className="stats" style={{ padding: "0 12px" }}>
            {overview
              ? `overview · ${view.shown} connected`
              : `${focus?.canonical_name ?? ""} · ${view.shown} nodes`}
          </span>

          <div className="segmented">
            {!overview && [1, 2].map((h) => (
              <button
                key={h}
                className={`seg ${hops === h ? "active" : ""}`}
                onClick={() => setHops(h)}
              >
                {hops === h && <motion.div layoutId="seg-bg" className="seg-bg" />}
                <span style={{ position: "relative", zIndex: 1 }}>
                  {h} hop{h === 1 ? "" : "s"}
                </span>
              </button>
            ))}
            <div style={{ width: 1, background: "var(--border)", margin: "8px 6px" }} />
            <button className={`seg ${overview ? "active" : ""}`} onClick={() => setOverview((v) => !v)}>
              {overview && <motion.div layoutId="seg-bg" className="seg-bg" />}
              <span style={{ position: "relative", zIndex: 1 }}>Whole Graph</span>
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
          <Background variant={BackgroundVariant.Dots} gap={24} size={2} color="var(--border-med)" />
          <Controls showInteractive={false} style={{ bottom: 80, right: 24, boxShadow: "0 4px 20px rgba(0,0,0,0.3)", border: "1px solid var(--border-med)", borderRadius: 8, overflow: "hidden" }} />
        </ReactFlow>

        <div className="legend">
          {usedTypes.map((t) => (
            <div className="legend-item" key={t}>
              <span className="swatch" style={{ background: TYPE_COLORS[t] ?? "#999" }} />
              {t}
            </div>
          ))}
        </div>

        <AnimatePresence>
          {!overview && view.shown === 1 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="hint"
            >
              This concept has no relationships — the source material never explicitly
              stated one. Edges are only created where the text supports them.
            </motion.div>
          )}
        </AnimatePresence>
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

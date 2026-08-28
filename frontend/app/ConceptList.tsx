"use client";

import { useMemo } from "react";
import type { ConceptEdge, ConceptNode } from "@/lib/graph";

type Props = {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
  focusId: string | null;
  search: string;
  onSearch: (v: string) => void;
  onFocus: (id: string) => void;
};

/**
 * Browsable index of every concept.
 *
 * The graph canvas answers "how does this connect"; it is a poor way to find a
 * concept by name among dozens. The list is the entry point — scan or search,
 * then focus the graph on one concept.
 */
export default function ConceptList({ concepts, edges, focusId, search, onSearch, onFocus }: Props) {
  const degree = useMemo(() => {
    const d = new Map<string, number>();
    for (const e of edges) {
      d.set(e.source_concept_id, (d.get(e.source_concept_id) ?? 0) + 1);
      d.set(e.target_concept_id, (d.get(e.target_concept_id) ?? 0) + 1);
    }
    return d;
  }, [edges]);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = q
      ? concepts.filter(
          (c) =>
            c.canonical_name.toLowerCase().includes(q) ||
            c.aliases?.some((a) => a.toLowerCase().includes(q)) ||
            c.keywords?.some((k) => k.toLowerCase().includes(q))
        )
      : concepts;
    // Most-connected first: hubs are the useful starting points for exploring.
    return [...filtered].sort(
      (a, b) =>
        (degree.get(b.concept_id) ?? 0) - (degree.get(a.concept_id) ?? 0) ||
        b.occurrence_count - a.occurrence_count ||
        a.canonical_name.localeCompare(b.canonical_name)
    );
  }, [concepts, search, degree]);

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <input
          className="search"
          placeholder="Search concepts…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
        <div className="sidebar-count">
          {shown.length} of {concepts.length} concepts
        </div>
      </div>

      <div className="concept-list">
        {shown.map((c) => {
          const d = degree.get(c.concept_id) ?? 0;
          return (
            <button
              key={c.concept_id}
              className={`concept-row${c.concept_id === focusId ? " active" : ""}`}
              onClick={() => onFocus(c.concept_id)}
            >
              <span className="concept-row-name">{c.canonical_name}</span>
              <span className="concept-row-meta">
                {d > 0 ? `${d} link${d === 1 ? "" : "s"}` : "no links"}
                {c.filenames.length > 1 && ` · ${c.filenames.length} docs`}
              </span>
            </button>
          );
        })}
        {shown.length === 0 && <div className="sidebar-empty">No concepts match “{search}”.</div>}
      </div>
    </aside>
  );
}

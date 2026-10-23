"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import clsx from "clsx";
import type { ConceptEdge, ConceptNode } from "@/lib/graph";

type Props = {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
  focusId: string | null;
  search: string;
  onSearch: (v: string) => void;
  onFocus: (id: string) => void;
};

const listVariant = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.025 } },
};

const itemVariant = {
  hidden: { opacity: 0, x: -12 },
  visible: { opacity: 1, x: 0 },
};

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
    // Most-connected first
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
        <div className="search-wrapper">
          <Search size={14} className="search-icon" />
          <input
            className="search"
            placeholder="Search concepts…"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
          />
        </div>
        <div className="sidebar-count">
          {shown.length} of {concepts.length} concepts
        </div>
      </div>

      <div className="concept-list">
        <motion.div variants={listVariant} initial="hidden" animate="visible">
          {shown.map((c) => {
            const d = degree.get(c.concept_id) ?? 0;
            return (
              <motion.button
                key={c.concept_id}
                variants={itemVariant}
                className={clsx("concept-row", c.concept_id === focusId && "active")}
                onClick={() => onFocus(c.concept_id)}
              >
                <span className="concept-row-name">{c.canonical_name}</span>
                <span className="concept-row-meta">
                  <span className="conn-pill">{d > 0 ? `${d} links` : "no links"}</span>
                  {c.filenames.length > 1 && <span>· {c.filenames.length} docs</span>}
                </span>
              </motion.button>
            );
          })}
        </motion.div>
        {shown.length === 0 && <div className="sidebar-empty">No concepts match “{search}”.</div>}
      </div>
    </aside>
  );
}

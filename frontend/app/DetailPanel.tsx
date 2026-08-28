"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ExternalLink } from "lucide-react";
import type { ConceptEdge, ConceptNode } from "@/lib/graph";
import { TYPE_COLORS } from "@/lib/graph";

type Props = {
  concept: ConceptNode | null;
  edges: ConceptEdge[];
  conceptsById: Record<string, ConceptNode>;
  onSelect: (id: string) => void;
  onClose: () => void;
};

export default function DetailPanel({ concept, edges, conceptsById, onSelect, onClose }: Props) {
  const [tab, setTab] = useState<"def" | "ev" | "rel">("def");

  return (
    <AnimatePresence>
      {concept && (
        <motion.aside
          initial={{ x: 400, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 400, opacity: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          className="panel"
        >
          <div className="panel-head">
            <button className="close" onClick={onClose} aria-label="Close">
              <X size={20} />
            </button>
            <h2>{concept.canonical_name}</h2>
            
            <div className="tabs">
              {["def", "ev", "rel"].map((t) => (
                <button
                  key={t}
                  className={`tab ${tab === t ? "active" : ""}`}
                  onClick={() => setTab(t as any)}
                >
                  {t === "def" ? "Definition" : t === "ev" ? "Evidence" : "Relationships"}
                  {tab === t && (
                    <motion.div
                      layoutId="tab-indicator"
                      className="tab-indicator"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="panel-body">
            {tab === "def" && <DefinitionTab concept={concept} />}
            {tab === "ev" && <EvidenceTab concept={concept} />}
            {tab === "rel" && (
              <RelationshipsTab
                concept={concept}
                edges={edges}
                conceptsById={conceptsById}
                onSelect={onSelect}
              />
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function DefinitionTab({ concept }: { concept: ConceptNode }) {
  return (
    <>
      <div className="node-meta" style={{ marginBottom: 16 }}>
        {concept.occurrence_count} mention{concept.occurrence_count === 1 ? "" : "s"} ·{" "}
        {concept.filenames.length} document{concept.filenames.length === 1 ? "" : "s"} ·{" "}
        confidence {concept.mean_confidence.toFixed(2)}
      </div>

      {concept.definition ? (
        <p className="definition">{concept.definition}</p>
      ) : (
        <div className="empty-state">No explicit definition found in text.</div>
      )}

      {concept.aliases?.length > 1 && (
        <>
          <h3>Also appears as</h3>
          <div className="tags">
            {concept.aliases.map((a) => (
              <span className="tag" key={a}>{a}</span>
            ))}
          </div>
        </>
      )}

      {concept.keywords?.length > 0 && (
        <>
          <h3>Keywords</h3>
          <div className="tags">
            {concept.keywords.map((k) => (
              <span className="tag" key={k}>{k}</span>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function EvidenceTab({ concept }: { concept: ConceptNode }) {
  return (
    <>
      {concept.evidence?.length > 0 ? (
        concept.evidence.map((ev, i) => (
          <div className="evidence" key={i}>
            “{ev}”
            <span className="src">
              {concept.filenames[0]}
              {concept.page_numbers?.length > 0 && ` · p${concept.page_numbers[0]}`}
            </span>
          </div>
        ))
      ) : (
        <div className="empty-state">No direct evidence clips available.</div>
      )}
      
      <h3 style={{ marginTop: 32 }}>Sources</h3>
      {concept.filenames.map((f, i) => (
        <div className="source-line" key={i}>
          {f}
          {concept.page_numbers?.length > 0 && (
            <span style={{ color: "var(--text-3)" }}> · p{concept.page_numbers.join(", ")}</span>
          )}
        </div>
      ))}
    </>
  );
}

function RelationshipsTab({
  concept,
  edges,
  conceptsById,
  onSelect,
}: {
  concept: ConceptNode;
  edges: ConceptEdge[];
  conceptsById: Record<string, ConceptNode>;
  onSelect: (id: string) => void;
}) {
  const related = edges.filter(
    (e) => e.source_concept_id === concept.concept_id || e.target_concept_id === concept.concept_id
  );

  if (related.length === 0) {
    return (
      <div className="empty-state">
        No relationships. The source material never explicitly stated one for this concept, and edges are only created where the text supports them.
      </div>
    );
  }

  return (
    <>
      <div className="node-meta" style={{ marginBottom: 16 }}>{related.length} connections</div>
      {related.map((e) => {
        const outgoing = e.source_concept_id === concept.concept_id;
        const otherId = outgoing ? e.target_concept_id : e.source_concept_id;
        const other = conceptsById[otherId];
        const evidence = e.evidence_texts?.[0] ?? "";
        const src = e.evidence_filenames?.[0] ?? "";
        const page = e.evidence_locations?.[0] ?? 0;
        
        return (
          <div className="rel" key={e.relationship_id} onClick={() => onSelect(otherId)}>
            <div className="rel-head">
              {!outgoing && <span className="rel-target">{other?.canonical_name ?? otherId}</span>}
              <span className="rel-type" style={{ color: TYPE_COLORS[e.type] ?? "#666" }}>
                {outgoing ? "" : "→ "}{e.type}{outgoing ? " →" : ""}
              </span>
              {outgoing && <span className="rel-target">{other?.canonical_name ?? otherId}</span>}
            </div>
            {evidence && (
              <div className="evidence" style={{ marginTop: 12, marginBottom: 0 }}>
                “{evidence}”
                {src && (
                  <span className="src">
                    {src}{page ? ` p${page}` : ""}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

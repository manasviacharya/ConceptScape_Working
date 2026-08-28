"use client";

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
  if (!concept) {
    return (
      <aside className="panel">
        <div className="empty">
          Select a concept to see its definition,
          <br />
          source evidence and relationships.
        </div>
      </aside>
    );
  }

  const related = edges.filter(
    (e) => e.source_concept_id === concept.concept_id || e.target_concept_id === concept.concept_id
  );

  return (
    <aside className="panel">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h2>{concept.canonical_name}</h2>
      <div className="node-meta">
        {concept.occurrence_count} mention{concept.occurrence_count === 1 ? "" : "s"} ·{" "}
        {concept.filenames.length} document{concept.filenames.length === 1 ? "" : "s"} ·{" "}
        confidence {concept.mean_confidence}
      </div>

      {concept.definition && <p className="definition">{concept.definition}</p>}

      {/* Evidence is shown verbatim with its page. This is the whole point of the
          grounding work — a reader can open the source and check the claim. */}
      {concept.evidence?.length > 0 && (
        <>
          <h3>Source evidence</h3>
          {concept.evidence.map((ev, i) => (
            <div className="evidence" key={i}>
              “{ev}”
              <span className="src">
                {concept.filenames[0]}
                {concept.page_numbers?.length > 0 && ` · p${concept.page_numbers[0]}`}
              </span>
            </div>
          ))}
        </>
      )}

      {related.length > 0 && (
        <>
          <h3>Relationships ({related.length})</h3>
          {related.map((e) => {
            const outgoing = e.source_concept_id === concept.concept_id;
            const otherId = outgoing ? e.target_concept_id : e.source_concept_id;
            const other = conceptsById[otherId];
            const evidence = e.evidence_texts?.[0] ?? "";
            const src = e.evidence_filenames?.[0] ?? "";
            const page = e.evidence_locations?.[0] ?? 0;
            return (
              <div className="rel" key={e.relationship_id}>
                {!outgoing && <span className="rel-target" onClick={() => onSelect(otherId)}>
                  {other?.canonical_name ?? otherId}
                </span>}
                <span className="rel-type" style={{ color: TYPE_COLORS[e.type] ?? "#666" }}>
                  {outgoing ? "" : "→ "}{e.type}{outgoing ? " →" : ""}
                </span>
                {outgoing && <span className="rel-target" onClick={() => onSelect(otherId)}>
                  {other?.canonical_name ?? otherId}
                </span>}
                {evidence && (
                  <div className="rel-evidence">
                    “{evidence}”
                    {src && <span className="src"> — {src}{page ? ` p${page}` : ""}</span>}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}

      {related.length === 0 && (
        <>
          <h3>Relationships</h3>
          <p className="node-meta">
            No relationships. The source material never explicitly stated one for this
            concept, and edges are only created where the text supports them.
          </p>
        </>
      )}

      <h3>Sources</h3>
      {concept.filenames.map((f, i) => (
        <div className="source-line" key={i}>
          {f}
          {concept.page_numbers?.length > 0 && (
            <span className="node-meta"> · p{concept.page_numbers.join(", ")}</span>
          )}
        </div>
      ))}

      {concept.aliases?.length > 1 && (
        <>
          <h3>Also appears as</h3>
          <div className="tags">
            {concept.aliases.map((a) => <span className="tag" key={a}>{a}</span>)}
          </div>
        </>
      )}

      {concept.keywords?.length > 0 && (
        <>
          <h3>Keywords</h3>
          <div className="tags">
            {concept.keywords.map((k) => <span className="tag" key={k}>{k}</span>)}
          </div>
        </>
      )}
    </aside>
  );
}

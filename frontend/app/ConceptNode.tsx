"use client";

import { Handle, Position, NodeProps } from "reactflow";
import type { ConceptNode as Concept } from "@/lib/graph";

export type ConceptNodeData = {
  concept: Concept;
  degree: number;
  depth?: number;
  selected?: boolean;
  dimmed?: boolean;
};

export default function ConceptNode({ data }: NodeProps<ConceptNodeData>) {
  const { concept, degree, depth, selected, dimmed } = data;
  const isolated = degree === 0;

  const classes = ["node"];
  if (depth === 0) classes.push("focus");
  if (depth === 2) classes.push("hop2");
  if (selected && depth !== 0) classes.push("selected");
  if (isolated) classes.push("isolated");
  if (dimmed) classes.push("dimmed");

  const docs = concept.filenames?.length ?? 0;

  return (
    <div className={classes.join(" ")} title={concept.definition}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="node-name">{concept.canonical_name}</div>
      <div className="node-meta">
        {concept.occurrence_count}× · {degree} link{degree === 1 ? "" : "s"}
        {docs > 1 && ` · ${docs} docs`}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

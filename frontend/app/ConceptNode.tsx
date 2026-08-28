"use client";

import { Handle, Position } from "reactflow";
import { motion } from "framer-motion";
import clsx from "clsx";
import type { ConceptNode as Concept } from "@/lib/graph";

export default function ConceptNode({
  data,
  selected,
}: {
  data: { concept: Concept; degree: number; depth: number };
  selected?: boolean;
}) {
  const { concept, degree, depth } = data;
  const isFocus = selected;
  const isIsolated = degree === 0;

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ visibility: "hidden" }} />
      <motion.div
        whileHover={{ scale: 1.02 }}
        className={clsx(
          "node",
          isIsolated && "isolated",
          isFocus && "focus",
          !isFocus && depth === 2 && "hop2"
        )}
      >
        <div className="node-header">
          <div className="node-icon">{concept.canonical_name.charAt(0).toUpperCase()}</div>
          {degree > 0 && <span className="node-degree">{degree}</span>}
        </div>
        <div className="node-name">{concept.canonical_name}</div>
      </motion.div>
      <Handle type="source" position={Position.Bottom} style={{ visibility: "hidden" }} />
    </>
  );
}

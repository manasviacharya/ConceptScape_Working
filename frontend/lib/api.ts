export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Citation = {
  index: number;
  kind: "concept" | "relationship" | "chunk";
  text: string;
  concept_name: string;
  filename: string;
  page_number: number;
  chunk_id: string;
  relationship: string;
};

export type AskResponse = {
  query: string;
  query_type: "A" | "B" | "C";
  query_type_label: string;
  answer: string;
  sufficient_evidence: boolean;
  flags: string[];
  concepts_identified: string[];
  retriever_used: string;
  model_used: string;
  used_citations: number[];
  citations: Citation[];
};

export async function ask(query: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

// Flags come from the pipeline as machine-readable slugs. The UI explains what
// each one means rather than showing the raw token — a reader needs to know
// whether to trust the answer, not what the code called the problem.
export const FLAG_LABELS: Record<string, string> = {
  thin_evidence: "Few sources found — treat this answer with caution",
  no_evidence_retrieved: "Nothing in the indexed material matched this question",
  hallucinated_citation: "The model cited a source that does not exist; it was removed",
  invalid_citation_removed: "An invalid citation reference was removed",
  uncited_answer: "The answer made claims without citing a source",
  partial_evidence: "The evidence only partly covers this question",
  conflicting_sources: "Sources disagree with each other",
  ocr_quality: "Quoted text is garbled — it came from a scanned page",
  generation_failed: "Answer generation failed — all model providers were unavailable",
  parse_failure: "The model response could not be parsed",
};

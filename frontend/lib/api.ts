import { authHeaders } from "./auth";

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
  session_id?: string;
};

export async function ask(query: string, sessionId?: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ query, ...(sessionId ? { session_id: sessionId } : {}) }),
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

// --- Health / Stats ---
export type HealthStatus = {
  status: string;
  artifacts: {
    concepts: boolean;
    relationships: boolean;
    graph: boolean;
    chunks: boolean;
  };
};

export async function getHealth(): Promise<HealthStatus> {
  const r = await fetch(`${API_BASE}/health`);
  if (!r.ok) throw new Error("Backend unavailable");
  return r.json();
}

// --- Upload & Pipeline API ---

export type Doc = { filename: string; size_bytes: number; suffix: string; status?: string; error?: string | null; version?: number; uploaded_at?: string | null; processed_at?: string | null };
export type Stage = { key: string; label: string; status: string; detail: string; seconds: number };
export type PipelineStatus = {
  running: boolean;
  current: string | null;
  error: string | null;
  stages: Stage[];
  elapsed: number;
};

export async function listDocuments(): Promise<{ documents: Doc[] }> {
  const r = await fetch(`${API_BASE}/documents`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to list documents");
  const data = await r.json();
  return { documents: data.documents ?? [] };
}

export async function uploadDocument(file: File): Promise<void> {
  const body = new FormData();
  body.append("files", file);
  const r = await fetch(`${API_BASE}/documents`, { method: "POST", headers: authHeaders(), body });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.detail ?? `Upload failed for ${file.name}`);
  }
}

export type ChatSession = { id: string; title: string; created_at?: string };

export async function listChatSessions(): Promise<ChatSession[]> {
  const r = await fetch(`${API_BASE}/chat/sessions`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load conversations");
  return (await r.json()).sessions ?? [];
}

export async function getChatSession(id: string): Promise<{ id: string; title: string; messages: { role: string; content: string; metadata?: AskResponse }[] }> {
  const r = await fetch(`${API_BASE}/chat/sessions/${encodeURIComponent(id)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load conversation");
  return r.json();
}

export async function renameChatSession(id: string, title: string): Promise<void> {
  const r = await fetch(`${API_BASE}/chat/sessions/${encodeURIComponent(id)}`, { method: "PATCH", headers: authHeaders(true), body: JSON.stringify({ title }) });
  if (!r.ok) throw new Error("Failed to rename conversation");
}

export async function deleteChatSession(id: string): Promise<void> {
  const r = await fetch(`${API_BASE}/chat/sessions/${encodeURIComponent(id)}`, { method: "DELETE", headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to delete conversation");
}

export async function addYouTube(url: string): Promise<void> {
  const r = await fetch(`${API_BASE}/documents/youtube`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ url }),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.detail ?? `Could not add YouTube video (HTTP ${r.status})`);
  }
}

export async function listWorkspaces(): Promise<{ id: string; name: string; role: string }[]> {
  const r = await fetch(`${API_BASE}/workspaces`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load workspaces");
  return (await r.json()).workspaces ?? [];
}

export async function createWorkspace(name: string): Promise<{ id: string; name: string }> {
  const r = await fetch(`${API_BASE}/workspaces`, { method: "POST", headers: authHeaders(true), body: JSON.stringify({ name }) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not create workspace");
  return r.json();
}

export async function renameWorkspace(id: string, name: string): Promise<void> {
  const r = await fetch(`${API_BASE}/workspaces/${id}`, { method: "PATCH", headers: authHeaders(true), body: JSON.stringify({ name }) });
  if (!r.ok) throw new Error("Could not rename workspace");
}

export async function deleteWorkspace(id: string): Promise<void> {
  const r = await fetch(`${API_BASE}/workspaces/${id}`, { method: "DELETE", headers: authHeaders() });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not delete workspace");
}

export async function listMembers(workspaceId: string): Promise<{ id: string; email: string; display_name: string; role: string }[]> {
  const r = await fetch(`${API_BASE}/workspaces/${workspaceId}/members`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load workspace members");
  return (await r.json()).members ?? [];
}

export async function addMember(workspaceId: string, email: string): Promise<void> {
  const r = await fetch(`${API_BASE}/workspaces/${workspaceId}/members`, { method: "POST", headers: authHeaders(true), body: JSON.stringify({ email }) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not add member");
}

export async function removeDocument(filename: string): Promise<void> {
  const r = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, { method: "DELETE", headers: authHeaders() });
  if (!r.ok) throw new Error(`Failed to remove ${filename}`);
}

export async function replaceDocument(filename: string, file: File): Promise<void> {
  const body = new FormData(); body.append("file", file);
  const r = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, { method: "PUT", headers: authHeaders(), body });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Failed to replace document");
}

export async function reprocessDocument(filename: string): Promise<void> {
  const r = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}/reprocess`, { method: "POST", headers: authHeaders() });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Failed to queue document");
}

export async function restoreDocumentVersion(filename: string, version: number): Promise<void> {
  const r = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}/versions/${version}/restore`, { method: "POST", headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to restore document version");
}

export function documentPreviewUrl(filename: string): string {
  return `${API_BASE}/documents/${encodeURIComponent(filename)}/preview`;
}

export async function loadDocumentPreview(filename: string): Promise<string> {
  const r = await fetch(documentPreviewUrl(filename), { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load document preview");
  return URL.createObjectURL(await r.blob());
}

export async function getStatus(): Promise<PipelineStatus> {
  const r = await fetch(`${API_BASE}/pipeline/status`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to get pipeline status");
  return r.json();
}

/**
 * Fetch the concept graph from the API rather than a build-time JSON copy.
 *
 * A static file only changes when someone re-runs the sync script, so the graph
 * silently showed stale data after a pipeline run. Reading the API means an
 * upload is reflected as soon as the page is revisited.
 */
export async function getGraph(filters: { document?: string; relation_type?: string; min_confidence?: number; connected_only?: boolean } = {}): Promise<{ nodes: any[]; edges: any[] }> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") params.set(key, String(value)); });
  const res = await fetch(`${API_BASE}/graph${params.toString() ? `?${params}` : ""}`, { cache: "no-store", headers: authHeaders() });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getGraphNeighbors(conceptId: string, hops = 1): Promise<{ nodes: any[]; edges: any[] }> {
  const r = await fetch(`${API_BASE}/graph/neighbors/${encodeURIComponent(conceptId)}?hops=${hops}`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load graph neighbors");
  return r.json();
}

export async function getGraphPaths(sourceId: string, targetId: string, maxHops = 4): Promise<{ paths: any[] }> {
  const r = await fetch(`${API_BASE}/graph/paths?source_id=${encodeURIComponent(sourceId)}&target_id=${encodeURIComponent(targetId)}&max_hops=${maxHops}`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to find graph paths");
  return r.json();
}

export async function getPrerequisiteGraph(conceptId: string): Promise<{ nodes: any[]; edges: any[] }> {
  const r = await fetch(`${API_BASE}/graph/prerequisites/${encodeURIComponent(conceptId)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load prerequisite graph");
  return r.json();
}

export async function getLearningPath(conceptId: string): Promise<any> {
  const r = await fetch(`${API_BASE}/learning-paths/${encodeURIComponent(conceptId)}`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load learning path");
  return r.json();
}

export async function explainConcept(conceptId: string, mode: "simple" | "step_by_step" | "source_example" | "compare", sessionId?: string): Promise<AskResponse> {
  const r = await fetch(`${API_BASE}/explain`, { method: "POST", headers: authHeaders(true), body: JSON.stringify({ concept_id: conceptId, mode, ...(sessionId ? { session_id: sessionId } : {}) }) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not explain concept");
  return r.json();
}

export async function getQuiz(conceptId: string, type = "multiple_choice"): Promise<any> {
  const r = await fetch(`${API_BASE}/quiz/${encodeURIComponent(conceptId)}?question_type=${type}`, { headers: authHeaders() });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not generate quiz");
  return r.json();
}

export async function submitQuiz(conceptId: string, questionType: string, answer: string): Promise<any> {
  const r = await fetch(`${API_BASE}/quiz/attempts`, { method: "POST", headers: authHeaders(true), body: JSON.stringify({ concept_id: conceptId, question_type: questionType, answer }) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not submit quiz");
  return r.json();
}

export async function updateConceptProgress(conceptId: string, status: string, confidence: number): Promise<void> {
  await fetch(`${API_BASE}/progress/concepts/${encodeURIComponent(conceptId)}`, { method: "POST", headers: authHeaders(true), body: JSON.stringify({ status, confidence }) });
}

export async function updatePathProgress(conceptId: string, status: string): Promise<void> {
  await fetch(`${API_BASE}/progress/paths/${encodeURIComponent(conceptId)}`, { method: "POST", headers: authHeaders(true), body: JSON.stringify({ status }) });
}

export async function getProgress(): Promise<any> {
  const r = await fetch(`${API_BASE}/progress`, { headers: authHeaders() });
  if (!r.ok) throw new Error("Failed to load progress");
  return r.json();
}

export async function getQualityReport(): Promise<any> {
  const r = await fetch(`${API_BASE}/quality/report`, { headers: authHeaders() });
  if (!r.ok) throw new Error("No quality report available");
  return r.json();
}

export async function reviewQuality(targetType: string, targetId: string, status: string, note?: string): Promise<void> {
  const r = await fetch(`${API_BASE}/quality/reviews/${targetType}/${encodeURIComponent(targetId)}`, { method: "PATCH", headers: authHeaders(true), body: JSON.stringify({ status, note }) });
  if (!r.ok) throw new Error("Could not save quality review");
}

export async function getAdminOverview(): Promise<any> {
  const r = await fetch(`${API_BASE}/admin/overview`, { headers: authHeaders() });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Admin access required");
  return r.json();
}

export async function runPipeline(): Promise<void> {
  const r = await fetch(`${API_BASE}/pipeline/run`, { method: "POST", headers: authHeaders() });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.reason ?? "Could not start the pipeline.");
  }
}


/** Render a source position in the unit it was measured in. */
export function formatLocation(type: string, n: number): string {
  if (!n && n !== 0) return "";
  if (type === "timestamp") {
    const m = Math.floor(n / 60), s = n % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }
  if (type === "slide") return `slide ${n}`;
  if (type === "page") return `p${n}`;
  return String(n);
}

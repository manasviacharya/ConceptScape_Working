"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

type Doc = { filename: string; size_bytes: number; suffix: string };
type Stage = { key: string; label: string; status: string; detail: string; seconds: number };
type RunStatus = {
  running: boolean;
  current: string | null;
  error: string | null;
  stages: Stage[];
  elapsed: number;
};

const ACCEPT = ".pdf,.pptx,.ppt,.png,.jpg,.jpeg,.webp";

export default function UploadPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const loadDocs = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/documents`);
      setDocs((await r.json()).documents ?? []);
      setError("");
    } catch {
      setError(`Cannot reach the API at ${API_BASE}. Start it with: python run_api.py`);
    }
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/pipeline/status`);
      setStatus(await r.json());
    } catch {
      /* the documents call already reports connectivity */
    }
  }, []);

  useEffect(() => {
    loadDocs();
    loadStatus();
  }, [loadDocs, loadStatus]);

  // Poll only while a run is active. A full run takes minutes, so the UI must
  // show which stage is executing rather than an indefinite spinner.
  useEffect(() => {
    if (!status?.running) return;
    const t = setInterval(() => {
      loadStatus();
      loadDocs();
    }, 2000);
    return () => clearInterval(t);
  }, [status?.running, loadStatus, loadDocs]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setNotice("");
    const body = new FormData();
    Array.from(files).forEach((f) => body.append("files", f));
    try {
      const r = await fetch(`${API_BASE}/documents`, { method: "POST", body });
      const data = await r.json();
      const parts: string[] = [];
      if (data.saved?.length) parts.push(`${data.saved.length} file(s) uploaded`);
      for (const rej of data.rejected ?? []) parts.push(`${rej.filename}: ${rej.reason}`);
      setNotice(parts.join(" · "));
      await loadDocs();
    } catch (e: any) {
      setError(`Upload failed: ${e.message}`);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function remove(filename: string) {
    await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
    await loadDocs();
  }

  async function run() {
    setNotice("");
    const r = await fetch(`${API_BASE}/pipeline/run`, { method: "POST" });
    const data = await r.json();
    if (!data.started) setNotice(data.reason ?? "Could not start the pipeline.");
    await loadStatus();
  }

  const running = status?.running ?? false;
  const done = status?.stages?.every((s) => s.status === "done") && !running;

  return (
    <div className="chat-page">
      <header className="chat-head">
        <span className="title">ConceptScape</span>
        <nav className="nav">
          <Link href="/">Graph</Link>
          <Link href="/chat">Ask</Link>
          <span className="nav-active">Documents</span>
        </nav>
      </header>

      <div className="chat-scroll">
        {error && <div className="warn">{error}</div>}
        {notice && <div className="warn subtle">{notice}</div>}

        <div
          className={`dropzone${dragging ? " dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            upload(e.dataTransfer.files);
          }}
          onClick={() => fileInput.current?.click()}
        >
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={ACCEPT}
            hidden
            onChange={(e) => upload(e.target.files)}
          />
          <div className="dz-title">{uploading ? "Uploading…" : "Drop documents here"}</div>
          <div className="dz-sub">PDF · PPTX · PNG · JPG · WEBP — or click to browse</div>
        </div>

        <div className="doc-head">
          <h3>Documents ({docs.length})</h3>
          <button className="primary" onClick={run} disabled={running || docs.length === 0}>
            {running ? "Processing…" : "Process documents"}
          </button>
        </div>

        {docs.length === 0 && (
          <div className="sidebar-empty">No documents yet. Add some to build the graph.</div>
        )}

        <div className="doc-list">
          {docs.map((d) => (
            <div className="doc-row" key={d.filename}>
              <span className="doc-name">{d.filename}</span>
              <span className="doc-size">{(d.size_bytes / 1_000_000).toFixed(1)} MB</span>
              <button className="doc-del" onClick={() => remove(d.filename)} disabled={running}>
                remove
              </button>
            </div>
          ))}
        </div>

        {status?.stages?.length > 0 && (
          <>
            <div className="doc-head">
              <h3>
                Pipeline {running ? `· running (${status.elapsed}s)` : done ? "· complete" : "· last run"}
              </h3>
            </div>

            {status.error && <div className="warn">{status.error}</div>}

            <div className="stages">
              {status.stages.map((s) => (
                <div className={`stage ${s.status}`} key={s.key}>
                  <span className="stage-dot" />
                  <span className="stage-label">
                    {s.label}
                    {s.detail && <span className="stage-detail">{s.detail}</span>}
                  </span>
                  <span className="stage-status">
                    {s.status === "done" && `${s.seconds}s`}
                    {s.status === "running" && "running…"}
                    {s.status === "failed" && "failed"}
                    {s.status === "skipped" && "skipped"}
                    {s.status === "pending" && "waiting"}
                  </span>
                </div>
              ))}
            </div>

            {done && (
              <div className="warn subtle">
                Processing finished. The <Link href="/">graph</Link> and{" "}
                <Link href="/chat">chat</Link> now reflect these documents.
              </div>
            )}
            {status.error && (
              <div className="warn subtle">
                Every stage caches its work, so running again resumes from the failure
                rather than starting over. If an LLM quota was exhausted, wait and retry.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

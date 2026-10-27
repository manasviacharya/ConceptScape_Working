"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, FileText, Presentation, Image as ImageIcon, Trash2, CheckCircle2, Play, AlertCircle, Video } from "lucide-react";
import { type PipelineStatus, type Doc, listDocuments, uploadDocument, addYouTube, runPipeline, getStatus, removeDocument, replaceDocument, reprocessDocument, loadDocumentPreview } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import clsx from "clsx";
import { getToken } from "@/lib/auth";

export default function UploadPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [search, setSearch] = useState("");
  const [preview, setPreview] = useState<{ name: string; url: string } | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([listDocuments(), getStatus()]);
      setDocs(d.documents);
      setStatus(s);
    } catch (e: any) {
      setError(e.message || "Failed to connect to backend.");
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [refresh, router]);

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    if (busy) return;
    setBusy(true);
    setError("");

    for (const file of Array.from(e.dataTransfer.files)) {
      try {
        await uploadDocument(file);
      } catch (err: any) {
        setError(err.message || `Failed to upload ${file.name}`);
      }
    }
    await refresh();
    setBusy(false);
  };

  const onDelete = async (name: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await removeDocument(name);
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
    setBusy(false);
  };

  const onReprocess = async (name: string) => {
    if (busy) return;
    setBusy(true); setError("");
    try { await reprocessDocument(name); await runPipeline(); await refresh(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  const onReplace = async (name: string, file: File) => {
    setBusy(true); setError("");
    try { await replaceDocument(name, file); await refresh(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };

  const onPreview = async (name: string) => {
    try { setPreview({ name, url: await loadDocumentPreview(name) }); }
    catch (e: any) { setError(e.message); }
  };

  const onRun = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await runPipeline();
      await refresh();
    } catch (e: any) {
      setError(e.message);
    }
    setBusy(false);
  };

  const onAddYouTube = async () => {
    if (busy || !youtubeUrl.trim()) return;
    setBusy(true);
    setError("");
    try {
      await addYouTube(youtubeUrl.trim());
      setYoutubeUrl("");
      await refresh();
    } catch (e: any) {
      setError(e.message || "Could not add YouTube video.");
    } finally {
      setBusy(false);
    }
  };

  const isRunning = status?.running === true;

  return (
    <div className="upload-container">
      <Navbar rightSlot={
        <button 
          className="btn-primary" 
          disabled={docs.length === 0 || isRunning || busy} 
          onClick={onRun}
        >
          {isRunning ? "Pipeline Running…" : "Run Pipeline"}
          <Play size={14} />
        </button>
      } />

      {error && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="warn">
          <AlertCircle size={18} />
          {error}
        </motion.div>
      )}

      <div
        className={clsx("dropzone", drag && "dragging")}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => document.getElementById("file-upload-input")?.click()}
        style={{ cursor: "pointer" }}
      >
        <input
          id="file-upload-input"
          type="file"
          multiple
          style={{ display: "none" }}
          onChange={async (e) => {
            if (busy || !e.target.files) return;
            setBusy(true);
            setError("");
            for (const file of Array.from(e.target.files)) {
              try {
                await uploadDocument(file);
              } catch (err: any) {
                setError(err.message || `Failed to upload ${file.name}`);
              }
            }
            await refresh();
            setBusy(false);
          }}
        />
        <motion.div 
          animate={drag ? { y: [0, -8, 0] } : {}} 
          transition={{ repeat: drag ? Infinity : 0, duration: 0.8 }}
        >
          <UploadCloud size={48} strokeWidth={1.5} className="dz-icon" />
        </motion.div>
        <div>
          <div className="dz-title">Drag & Drop Documents Here</div>
          <div className="dz-sub">Supports PDF, PPTX, JPG, PNG, and YouTube links below</div>
        </div>
      </div>

      <div className="doc-head">
        <h3><Video size={17} style={{ verticalAlign: "-3px", marginRight: 6 }} />Add YouTube video</h3>
      </div>
      <div className="composer" style={{ marginBottom: 24 }}>
        <input
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          placeholder="Paste a YouTube URL"
          disabled={busy || isRunning}
          style={{ flex: 1, background: "transparent", border: 0, outline: 0, color: "inherit" }}
        />
        <button className="btn-primary" onClick={onAddYouTube} disabled={!youtubeUrl.trim() || busy || isRunning}>
          Add video
        </button>
      </div>

      <div className="doc-head">
        <h3>Indexed Documents ({docs.length})</h3>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search documents…" style={{ marginLeft: "auto", maxWidth: 240 }} />
      </div>
      
      <div className="doc-list">
        <AnimatePresence>
          {docs.length === 0 && (
            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}
            >
              No documents uploaded. The knowledge graph is empty.
            </motion.div>
          )}
          {docs.filter((doc) => doc.filename.toLowerCase().includes(search.toLowerCase())).map((doc, i) => (
            <motion.div 
              key={doc.filename}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ delay: i * 0.05 }}
              className="doc-row"
            >
              <DocIcon name={doc.filename} />
              <div className="doc-info">
                <span className="doc-name">{doc.filename}</span>
                <span className="stage-status">{doc.status ?? "uploaded"}{doc.version && ` · v${doc.version}`}{doc.size_bytes ? ` · ${Math.round(doc.size_bytes / 1024)} KB` : ""}</span>
                {doc.error && <span className="stage-detail">{doc.error}</span>}
              </div>
              <button className="doc-del" onClick={() => onPreview(doc.filename)} title="Preview source">◉</button>
              <label className="doc-del" title="Replace document" style={{ cursor: "pointer" }}>
                ↻<input type="file" hidden onChange={(e) => { const file = e.target.files?.[0]; if (file) onReplace(doc.filename, file); }} />
              </label>
              <button className="doc-del" onClick={() => onReprocess(doc.filename)} disabled={isRunning || busy} title="Reprocess document">⟳</button>
              <button 
                className="doc-del" 
                onClick={() => onDelete(doc.filename)} 
                disabled={isRunning || busy}
                title="Remove document"
              >
                <Trash2 size={16} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {status && (
        <>
          <div className="doc-head">
            <h3>Pipeline Status</h3>
          </div>
          <div className="stages">
            {status.stages.map((st, i) => (
              <motion.div 
                key={st.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className={clsx("stage", st.status)}
              >
                <div className="stage-icon">
                  {st.status === "done" ? <CheckCircle2 size={14} /> : 
                   st.status === "running" ? <div className="spinner" style={{ width: 12, height: 12, border: "2px solid", borderTopColor: "transparent", borderRadius: "50%" }} /> : 
                   <div style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />}
                </div>
                <div className="stage-content">
                  <span className="stage-label">{st.label.replace(/_/g, " ")}</span>
                  <span className="stage-status">{st.status}</span>
                  {st.detail && <span className="stage-detail">{st.detail}</span>}
                </div>
                {st.status === "running" && <div className="stage-progress" />}
              </motion.div>
            ))}
          </div>
        </>
      )}
      {preview && <div className="modal-backdrop" onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}><div className="modal" onClick={(e) => e.stopPropagation()}><button className="close" onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}>×</button><h3>{preview.name}</h3>{/\.(png|jpg|jpeg|webp)$/i.test(preview.name) ? <img src={preview.url} alt={preview.name} style={{ maxWidth: "100%", maxHeight: "70vh" }} /> : <iframe src={preview.url} title={preview.name} style={{ width: "100%", height: "70vh", border: 0 }} />}</div></div>}
    </div>
  );
}

function DocIcon({ name }: { name: string }) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return <FileText size={20} className="doc-icon" />;
  if (ext === "pptx" || ext === "ppt") return <Presentation size={20} className="doc-icon" />;
  if (["png", "jpg", "jpeg", "webp"].includes(ext || "")) return <ImageIcon size={20} className="doc-icon" />;
  if (ext === "yt" || ext === "youtube") return <Video size={20} className="doc-icon" />;
  return <FileText size={20} className="doc-icon" />;
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, FileText, Presentation, Image as ImageIcon, Trash2, CheckCircle2, Play, AlertCircle } from "lucide-react";
import { type PipelineStatus, listDocuments, uploadDocument, runPipeline, getStatus, removeDocument } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import clsx from "clsx";

export default function UploadPage() {
  const [docs, setDocs] = useState<string[]>([]);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [refresh]);

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
          <div className="dz-sub">Supports PDF, PPTX, JPG, PNG (or click to select files)</div>
        </div>
      </div>

      <div className="doc-head">
        <h3>Indexed Documents</h3>
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
          {docs.map((doc, i) => (
            <motion.div 
              key={doc}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ delay: i * 0.05 }}
              className="doc-row"
            >
              <DocIcon name={doc} />
              <div className="doc-info">
                <span className="doc-name">{doc}</span>
              </div>
              <button 
                className="doc-del" 
                onClick={() => onDelete(doc)} 
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
    </div>
  );
}

function DocIcon({ name }: { name: string }) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return <FileText size={20} className="doc-icon" />;
  if (ext === "pptx" || ext === "ppt") return <Presentation size={20} className="doc-icon" />;
  if (["png", "jpg", "jpeg", "webp"].includes(ext || "")) return <ImageIcon size={20} className="doc-icon" />;
  return <FileText size={20} className="doc-icon" />;
}

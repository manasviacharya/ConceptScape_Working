"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Send, FileText, X } from "lucide-react";
import { FLAG_LABELS, ask, deleteChatSession, getChatSession, listChatSessions, renameChatSession, type AskResponse, type Citation, type ChatSession } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { getToken } from "@/lib/auth";

type Turn = {
  query: string;
  answer?: string;
  result?: AskResponse;
  error?: string;
  pending?: boolean;
};

const EXAMPLES = [
  "what does mini-batch SGD require?",
  "what is a learning rate?",
  "how do I stop my model overshooting the minimum?",
];

export default function ChatPage() {
  const router = useRouter();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else listChatSessions().then(setSessions).catch(() => undefined);
  }, [router]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function openSession(id: string) {
    const session = await getChatSession(id);
    setSessionId(session.id);
    const restored: Turn[] = [];
    for (const message of session.messages) {
      if (message.role === "user") restored.push({ query: message.content });
      else if (restored.length && message.metadata) restored[restored.length - 1].result = message.metadata;
      else if (restored.length) restored[restored.length - 1].answer = message.content;
    }
    setTurns(restored);
  }

  async function renameSession(session: ChatSession) {
    const title = window.prompt("Conversation name", session.title);
    if (!title?.trim()) return;
    await renameChatSession(session.id, title.trim());
    setSessions(await listChatSessions());
  }

  async function removeSession(id: string) {
    if (!window.confirm("Delete this conversation?")) return;
    await deleteChatSession(id);
    if (sessionId === id) { setSessionId(undefined); setTurns([]); }
    setSessions(await listChatSessions());
  }

  async function submit(query: string) {
    const q = query.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { query: q, pending: true }]);

    try {
      const result = await ask(q, sessionId);
      if (result.session_id) setSessionId(result.session_id);
      listChatSessions().then(setSessions).catch(() => undefined);
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { query: q, result } : turn)));
    } catch (e: any) {
      setTurns((t) =>
        t.map((turn, i) => (i === t.length - 1 ? { query: q, error: e.message } : turn))
      );
    } finally {
      setBusy(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  };

  return (
    <div className="chat-container">
      <Navbar />

      <div className="chat-inner">
        {sessions.length > 0 && (
          <aside style={{ width: 220, padding: "12px 8px", borderRight: "1px solid var(--border)", overflowY: "auto" }}>
            <div className="sources-head" style={{ marginBottom: 8 }}>Conversations</div>
            {sessions.map((session) => <div key={session.id} style={{ display: "flex", gap: 4, marginBottom: 6 }}><button className="source" style={{ flex: 1, textAlign: "left" }} onClick={() => openSession(session.id)}>{session.title}</button><button className="doc-del" onClick={() => renameSession(session)} title="Rename">✎</button><button className="doc-del" onClick={() => removeSession(session.id)} title="Delete">×</button></div>)}
          </aside>
        )}
        <div className="chat-scroll">
          {turns.length === 0 && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="chat-intro"
            >
              <h2 className="chat-intro-title">Ask ConceptScape</h2>
              <p>
                Answers come only from your indexed documents. Every claim is cited back to a
                page you can check — and if the material does not answer the question, it says so
                rather than guessing.
              </p>
              <div className="examples">
                {EXAMPLES.map((e, i) => (
                  <motion.button
                    key={e}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    whileHover={{ y: -4, borderColor: "var(--accent)", color: "#fff" }}
                    className="example"
                    onClick={() => submit(e)}
                  >
                    {e}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {turns.map((turn, i) => (
            <motion.div 
              className="turn" 
              key={i}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 260, damping: 24 }}
            >
              <div className="q">{turn.query}</div>

              {turn.pending && (
                <div className="a pending">
                  <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    <span style={{ fontSize: 13, color: "var(--text-3)" }}>Searching the knowledge graph</span>
                    <div style={{ display: "flex", gap: "4px", marginLeft: 4 }}>
                      {[0, 1, 2].map((dot) => (
                        <motion.span
                          key={dot}
                          style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--text-3)" }}
                          animate={{ y: [0, -4, 0] }}
                          transition={{ duration: 0.6, repeat: Infinity, delay: dot * 0.15 }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {turn.error && (
                <div className="a error">
                  {turn.error}
                  <div className="hint-inline">
                    Is the API running? Start it with <code>python run_api.py</code>.
                  </div>
                </div>
              )}

              {turn.result && <AnswerBlock result={turn.result} onCite={setOpenCitation} />}
              {turn.answer && !turn.result && <div className="a"><div className="a-text">{turn.answer}</div></div>}
            </motion.div>
          ))}
          <div ref={endRef} />
        </div>

        <div className="composer-wrap">
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              submit(input);
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your documents… (Press Enter to send)"
              disabled={busy}
              rows={Math.min(5, input.split("\n").length || 1)}
            />
            <motion.button 
              whileTap={{ scale: 0.93 }}
              type="submit" 
              className="composer-btn"
              disabled={busy || !input.trim()}
            >
              <Send size={18} strokeWidth={2.5} />
            </motion.button>
          </form>
        </div>
      </div>

      <AnimatePresence>
        {openCitation && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-backdrop" 
            onClick={() => setOpenCitation(null)}
          >
            <motion.div 
              initial={{ y: 50, scale: 0.95 }}
              animate={{ y: 0, scale: 1 }}
              exit={{ y: 20, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="modal" 
              onClick={(e) => e.stopPropagation()}
            >
              <button className="close" onClick={() => setOpenCitation(null)}>
                <X size={20} />
              </button>
              <h3>
                {openCitation.relationship
                  ? "Relationship evidence"
                  : openCitation.concept_name || "Source text"}
              </h3>
              {openCitation.relationship && (
                <div className="modal-rel">{openCitation.relationship}</div>
              )}
              <blockquote>“{openCitation.text}”</blockquote>
              <div className="modal-src">
                <FileText size={14} />
                <span>
                  {openCitation.filename}
                  {openCitation.page_number > 0 && ` · page ${openCitation.page_number}`}
                </span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AnswerBlock({
  result,
  onCite,
}: {
  result: AskResponse;
  onCite: (c: Citation) => void;
}) {
  const byIndex = new Map(result.citations.map((c) => [c.index, c]));
  const used = result.used_citations
    .map((i) => byIndex.get(i))
    .filter(Boolean) as Citation[];

  return (
    <div className="a">
      <div className="a-meta">
        <motion.span 
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`badge type-${result.query_type}`}
        >
          <span className="badge-dot" />
          Type {result.query_type} · {result.query_type_label}
        </motion.span>
        <span className="badge">
          {result.retriever_used} retrieval
        </span>
        {result.concepts_identified.length > 0 && (
          <span className="badge">
            {result.concepts_identified.join(", ")}
          </span>
        )}
      </div>

      <div className="a-text">{renderWithCitations(result.answer, byIndex, onCite)}</div>
      <button className="btn-ghost" aria-label="Read answer aloud" onClick={() => { if (typeof window !== "undefined") { window.speechSynthesis.cancel(); window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.answer)); } }}>🔊 Read aloud</button>

      {!result.sufficient_evidence && (
        <div className="warn">
          The indexed material does not contain enough evidence to answer this.
        </div>
      )}

      {result.flags.map((f) => (
        <div className="warn subtle" key={f}>
          {FLAG_LABELS[f] ?? f}
        </div>
      ))}

      {used.length > 0 && (
        <div className="sources">
          <div className="sources-head">Sources</div>
          {used.map((c) => (
            <button className="source" key={c.index} onClick={() => onCite(c)}>
              <span className="cite-num">{c.index}</span>
              <div className="source-body">
                <span className="source-title">
                  {c.relationship || c.concept_name || "source text"}
                </span>
                <span className="source-where">
                  <FileText size={12} />
                  {c.filename}
                  {c.page_number > 0 && ` · p${c.page_number}`}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function renderWithCitations(
  text: string,
  byIndex: Map<number, Citation>,
  onCite: (c: Citation) => void
) {
  const parts: React.ReactNode[] = [];
  const re = /\[(\d+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const n = Number(m[1]);
    const cite = byIndex.get(n);
    parts.push(
      cite ? (
        <button className="cite" key={`${n}-${m.index}`} onClick={() => onCite(cite)} title={cite.text}>
          {n}
        </button>
      ) : (
        <span key={`${n}-${m.index}`}>[{n}]</span>
      )
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { FLAG_LABELS, ask, type AskResponse, type Citation } from "@/lib/api";

type Turn = {
  query: string;
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
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function submit(query: string) {
    const q = query.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { query: q, pending: true }]);

    try {
      const result = await ask(q);
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { query: q, result } : turn)));
    } catch (e: any) {
      setTurns((t) =>
        t.map((turn, i) => (i === t.length - 1 ? { query: q, error: e.message } : turn))
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-page">
      <header className="chat-head">
        <span className="title">ConceptScape</span>
        <nav className="nav">
          <Link href="/">Graph</Link>
          <span className="nav-active">Ask</span>
          <Link href="/upload">Documents</Link>
        </nav>
      </header>

      <div className="chat-scroll">
        {turns.length === 0 && (
          <div className="chat-intro">
            <h2>Ask the knowledge base</h2>
            <p>
              Answers come only from your indexed documents. Every claim is cited back to a
              page you can check — and if the material does not answer the question, it says so
              rather than guessing.
            </p>
            <div className="examples">
              {EXAMPLES.map((e) => (
                <button key={e} className="example" onClick={() => submit(e)}>
                  {e}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <div className="turn" key={i}>
            <div className="q">{turn.query}</div>

            {turn.pending && <div className="a pending">Searching the knowledge graph…</div>}

            {turn.error && (
              <div className="a error">
                {turn.error}
                <div className="hint-inline">
                  Is the API running? Start it with <code>python run_api.py</code>.
                </div>
              </div>
            )}

            {turn.result && <AnswerBlock result={turn.result} onCite={setOpenCitation} />}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your documents…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>

      {openCitation && (
        <div className="modal-backdrop" onClick={() => setOpenCitation(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="close" onClick={() => setOpenCitation(null)}>×</button>
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
              {openCitation.filename}
              {openCitation.page_number > 0 && ` · page ${openCitation.page_number}`}
            </div>
          </div>
        </div>
      )}
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
        <span className={`badge type-${result.query_type}`}>
          Type {result.query_type} · {result.query_type_label}
        </span>
        <span className="badge muted">{result.retriever_used} retrieval</span>
        {result.concepts_identified.length > 0 && (
          <span className="badge muted">{result.concepts_identified.join(", ")}</span>
        )}
      </div>

      <p className="a-text">{renderWithCitations(result.answer, byIndex, onCite)}</p>

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
              <span className="source-body">
                <span className="source-title">
                  {c.relationship || c.concept_name || "source text"}
                </span>
                <span className="source-where">
                  {c.filename}
                  {c.page_number > 0 && ` · p${c.page_number}`}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Turns "[3]" in the answer text into a clickable chip showing that evidence. */
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

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { explainConcept, getGraph, getLearningPath, getQuiz, submitQuiz, updateConceptProgress, updatePathProgress, type AskResponse } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function LearnPage() {
  const router = useRouter();
  const [concepts, setConcepts] = useState<any[]>([]);
  const [selected, setSelected] = useState("");
  const [path, setPath] = useState<any>(null);
  const [explanation, setExplanation] = useState<AskResponse | null>(null);
  const [quiz, setQuiz] = useState<any>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    getGraph().then((data) => { setConcepts(data.nodes); if (data.nodes[0]) setSelected(data.nodes[0].concept_id); }).catch((e) => setError(e.message));
  }, [router]);

  async function choose(id: string) {
    setSelected(id); setExplanation(null); setQuiz(null); setFeedback(null);
    try { setPath(await getLearningPath(id)); } catch (e: any) { setError(e.message); }
  }
  async function explain(mode: "simple" | "step_by_step" | "source_example" | "compare") {
    try { setExplanation(await explainConcept(selected, mode)); await updateConceptProgress(selected, "started", 0.3); } catch (e: any) { setError(e.message); }
  }
  async function makeQuiz(type: string) { try { setQuiz(await getQuiz(selected, type)); setAnswer(""); setFeedback(null); } catch (e: any) { setError(e.message); } }
  async function submit() { try { setFeedback(await submitQuiz(selected, quiz.question_type, answer)); } catch (e: any) { setError(e.message); } }

  const concept = concepts.find((item) => item.concept_id === selected);
  return <main className="upload-container"><Navbar /><h1>Learning path</h1>
    {error && <div className="warn">{error}</div>}
    <div className="composer"><select value={selected} onChange={(e) => choose(e.target.value)} style={{ flex: 1 }}><option value="">Choose a concept</option>{concepts.map((item) => <option key={item.concept_id} value={item.concept_id}>{item.canonical_name}</option>)}</select></div>
    {concept && <><div className="doc-head"><h3>{concept.canonical_name}</h3><button className="btn-primary" onClick={() => updateConceptProgress(selected, "learned", 1)}>Mark learned</button><button className="btn-ghost" onClick={() => updateConceptProgress(selected, "revisit", 0)}>Revisit</button></div>
      <div className="segmented" style={{ marginBottom: 18 }}>{(["simple", "step_by_step", "source_example", "compare"] as const).map((mode) => <button className="seg" key={mode} onClick={() => explain(mode)}>{mode.replaceAll("_", " ")}</button>)}</div>
      {explanation && <div className="a"><div className="a-text">{explanation.answer}</div><button className="btn-ghost" aria-label="Read explanation aloud" onClick={() => { window.speechSynthesis.cancel(); window.speechSynthesis.speak(new SpeechSynthesisUtterance(explanation.answer)); }}>🔊 Read aloud</button><div className="sources-head">Evidence-backed sources: {explanation.citations.length}</div></div>}
      {path && <div className="doc-row" style={{ display: "block" }}><strong>Learn before this</strong><div>{path.learn_before.length ? path.learn_before.map((item: any) => <span key={item.concept.concept_id} style={{ display: "inline-flex", gap: 4, margin: 4 }}><button className="source" onClick={() => choose(item.concept.concept_id)}>{item.concept.canonical_name} · {item.status}</button><button className="doc-del" aria-label={`Mark ${item.concept.canonical_name} complete`} onClick={() => updatePathProgress(item.concept.concept_id, "completed")}>✓</button></span>) : "No verified prerequisites found."}</div><strong>Learn next</strong><div>{path.learn_next.length ? path.learn_next.map((item: any) => <span key={item.concept.concept_id} style={{ display: "inline-flex", gap: 4, margin: 4 }}><button className="source" onClick={() => choose(item.concept.concept_id)}>{item.concept.canonical_name} · {item.status}</button><button className="doc-del" aria-label={`Mark ${item.concept.canonical_name} complete`} onClick={() => updatePathProgress(item.concept.concept_id, "completed")}>✓</button></span>) : "No verified next concepts found."}</div></div>}
      <div className="doc-head"><h3>Practice</h3><button className="btn-ghost" onClick={() => makeQuiz("multiple_choice")}>Multiple choice</button><button className="btn-ghost" onClick={() => makeQuiz("short_answer")}>Short answer</button><button className="btn-ghost" onClick={() => makeQuiz("relationship")}>Relationship</button></div>
      {quiz && <div className="composer" style={{ display: "block" }}><p>{quiz.question}</p>{quiz.options ? quiz.options.map((option: any) => <button className="source" key={option.id ?? option} aria-pressed={answer === (option.id ?? option)} onClick={() => setAnswer(option.id ?? option)}>{option.text ?? option}</button>) : <input aria-label="Quiz answer" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Your answer" />}<button className="btn-primary" onClick={submit} disabled={!answer}>Submit</button><div className="sources-head">Evidence: {quiz.citations?.map((citation: any) => `${citation.filename} — ${citation.text}`).join(" · ")}</div>{feedback && <div className={feedback.correct ? "success" : "warn"}>{feedback.explanation}<div className="sources-head">{feedback.citations?.map((citation: any) => citation.filename).join(", ")}</div></div>}</div>}
    </>}
  </main>;
}

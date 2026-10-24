"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { getProgress } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function ProgressPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (!getToken()) router.replace("/login"); else getProgress().then(setData).catch((e) => setError(e.message)); }, [router]);
  return <main className="upload-container"><Navbar /><h1>Progress & mastery</h1>{error && <div className="warn">{error}</div>}{data && <><div className="doc-row"><strong>Quiz accuracy</strong><span>{Math.round(data.quiz.accuracy * 100)}% · {data.quiz.correct}/{data.quiz.attempts} correct</span></div><div className="doc-head"><h3>By document</h3></div>{data.by_document.map((item: any) => <div className="doc-row" key={item.name}><span>{item.name}</span><span>{Math.round(item.mastery * 100)}% · {item.concepts} concepts</span></div>)}<div className="doc-head"><h3>By topic</h3></div>{data.by_topic.map((item: any) => <div className="doc-row" key={item.name}><span>{item.name}</span><span>{Math.round(item.mastery * 100)}% · {item.concepts} concepts</span></div>)}<div className="doc-head"><h3>Concepts</h3></div>{data.concepts.length === 0 && <div className="empty-state">Start learning concepts to see mastery here.</div>}{data.concepts.map((item: any) => <div className="doc-row" key={item.concept_id}><span>{item.concept_id}</span><span>{item.status} · confidence {item.confidence.toFixed(2)}{item.needs_review ? " · revisit" : ""}</span></div>)}</>}</main>;
}

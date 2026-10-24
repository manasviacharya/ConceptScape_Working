"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { getQualityReport, reviewQuality } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function QualityPage() {
  const router = useRouter();
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (!getToken()) router.replace("/login"); else getQualityReport().then(setReport).catch((e) => setError(e.message)); }, [router]);
  async function review(type: string, id: string, status: string) { try { await reviewQuality(type, id, status); } catch (e: any) { setError(e.message); } }
  return <main className="upload-container"><Navbar /><h1>Research quality review</h1>{error && <div className="warn">{error}</div>}{report && <><div className="doc-row"><span>Concepts</span><span>{report.concepts.total} total · {report.concepts.low_confidence.length} low confidence · {report.concepts.near_duplicates.length} possible duplicates</span></div><div className="doc-head"><h3>Low-confidence concepts</h3></div>{report.concepts.low_confidence.map((item: any) => <div className="doc-row" key={item.concept_id}><span>{item.canonical_name}</span><span>{item.mean_confidence?.toFixed?.(2)} <button className="btn-ghost" onClick={() => review("concept", item.concept_id, "approved")}>Approve</button><button className="btn-ghost" onClick={() => review("concept", item.concept_id, "rejected")}>Reject</button></span></div>)}<div className="doc-head"><h3>Near-duplicate candidates</h3></div>{report.concepts.near_duplicates.map((item: any) => <div className="doc-row" key={`${item.left}-${item.right}`}><span>{item.left} ↔ {item.right}</span><span>similarity {item.similarity}</span></div>)}</>}</main>;
}

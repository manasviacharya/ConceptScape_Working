"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { getAdminOverview } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function AdminPage() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (!getToken()) router.replace("/login"); else getAdminOverview().then(setData).catch((e) => setError(e.message)); }, [router]);
  return <main className="upload-container"><Navbar /><h1>Admin & support</h1>{error && <div className="warn">{error}</div>}{data && <><div className="doc-row"><span>{data.workspace.name}</span><span>{data.members} members · {data.documents} documents</span></div><div className="doc-head"><h3>Document state</h3></div>{Object.entries(data.document_status).map(([status, count]) => <div className="doc-row" key={status}><span>{status}</span><span>{String(count)}</span></div>)}<div className="doc-head"><h3>Recent jobs</h3></div>{data.jobs.map((job: any) => <div className="doc-row" key={job.id}><span>{job.id.slice(0, 8)}</span><span>{job.status}{job.error ? ` · ${job.error}` : ""}</span></div>)}</>}</main>;
}

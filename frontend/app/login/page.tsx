"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { saveSession } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/${register ? "register" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(register ? { email, password, display_name: name } : { email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? "Authentication failed");
      saveSession(data); router.push("/upload");
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  }

  return <main className="upload-container" style={{ maxWidth: 520, margin: "80px auto" }}>
    <h1>{register ? "Create your ConceptScape workspace" : "Welcome back"}</h1>
    <p style={{ color: "var(--text-3)" }}>Sign in to keep documents, graph data, and questions isolated to your workspace.</p>
    <form onSubmit={submit} className="composer" style={{ display: "flex", flexDirection: "column", gap: 14, padding: 24 }}>
      {register && <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" required />}
      <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" required />
      <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password (8+ characters)" minLength={8} required />
      {error && <div className="warn">{error}</div>}
      <button className="btn-primary" disabled={busy}>{busy ? "Please wait…" : register ? "Create workspace" : "Sign in"}</button>
    </form>
    <button className="btn-ghost" onClick={() => setRegister(!register)}>{register ? "Already have an account? Sign in" : "Need an account? Create one"}</button>
  </main>;
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { addMember, createWorkspace, deleteWorkspace, listMembers, listWorkspaces, renameWorkspace } from "@/lib/api";
import { getToken, getWorkspaceId, setWorkspaceId } from "@/lib/auth";

type Workspace = { id: string; name: string; role: string };

export default function WorkspacePage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const selected = getWorkspaceId();

  async function refresh() {
    const items = await listWorkspaces(); setWorkspaces(items);
    const id = getWorkspaceId() ?? items[0]?.id;
    if (id) { setWorkspaceId(id); setMembers(await listMembers(id)); }
  }
  useEffect(() => { if (!getToken()) router.replace("/login"); else refresh().catch((e) => setError(e.message)); }, [router]);

  async function makeWorkspace() {
    if (!name.trim()) return;
    try { const item = await createWorkspace(name.trim()); setWorkspaceId(item.id); setName(""); await refresh(); }
    catch (e: any) { setError(e.message); }
  }
  async function invite() {
    if (!selected || !email.trim()) return;
    try { await addMember(selected, email.trim()); setEmail(""); await refresh(); }
    catch (e: any) { setError(e.message); }
  }

  async function renameSelected() {
    const item = workspaces.find((workspace) => workspace.id === selected);
    const next = item && window.prompt("Workspace name", item.name);
    if (!selected || !next?.trim()) return;
    try { await renameWorkspace(selected, next.trim()); await refresh(); } catch (e: any) { setError(e.message); }
  }

  async function deleteSelected() {
    if (!selected || !window.confirm("Delete this workspace and all its documents?")) return;
    try { await deleteWorkspace(selected); localStorage.removeItem("conceptscape.workspace_id"); await refresh(); } catch (e: any) { setError(e.message); }
  }

  return <main className="upload-container"><Navbar /><h1>Workspace settings</h1>
    {error && <div className="warn">{error}</div>}
    <div className="doc-head"><h3>Your workspaces</h3></div>
    {workspaces.map((item) => <button key={item.id} className="source" style={{ display: "block", width: "100%", textAlign: "left", marginBottom: 8, borderColor: item.id === selected ? "var(--accent)" : undefined }} onClick={() => { setWorkspaceId(item.id); refresh(); }}>{item.name} · {item.role}</button>)}
    {selected && <div style={{ display: "flex", gap: 8, marginTop: 8 }}><button className="btn-ghost" onClick={renameSelected}>Rename workspace</button><button className="btn-ghost" onClick={deleteSelected}>Delete workspace</button></div>}
    <div className="composer" style={{ marginTop: 20 }}><input value={name} onChange={(e) => setName(e.target.value)} placeholder="New workspace name" /><button className="btn-primary" onClick={makeWorkspace}>Create</button></div>
    {selected && <><div className="doc-head"><h3>Members</h3></div>{members.map((member) => <div className="doc-row" key={member.id}>{member.display_name} · {member.email} · {member.role}</div>)}<div className="composer" style={{ marginTop: 12 }}><input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Member email" /><button className="btn-primary" onClick={invite}>Add member</button></div></>}
  </main>;
}

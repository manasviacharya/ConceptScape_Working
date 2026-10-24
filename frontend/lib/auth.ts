const TOKEN_KEY = "conceptscape.access_token";
const WORKSPACE_KEY = "conceptscape.workspace_id";

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: { id: string; email: string; display_name: string };
  workspace?: { id: string; name: string } | null;
};

export function getToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
}

export function getWorkspaceId(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(WORKSPACE_KEY);
}

export function setWorkspaceId(id: string): void {
  window.localStorage.setItem(WORKSPACE_KEY, id);
}

export function saveSession(data: AuthResponse): void {
  window.localStorage.setItem(TOKEN_KEY, data.access_token);
  if (data.workspace?.id) window.localStorage.setItem(WORKSPACE_KEY, data.workspace.id);
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(WORKSPACE_KEY);
}

export function authHeaders(json = false): HeadersInit {
  const headers: Record<string, string> = {};
  if (json) headers["Content-Type"] = "application/json";
  const token = getToken();
  const workspace = getWorkspaceId();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (workspace) headers["X-Workspace-ID"] = workspace;
  return headers;
}

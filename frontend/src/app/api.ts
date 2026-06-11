/** Session-cookie API client for the SPA (same-origin; CSRF on writes). */

export function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (method !== "GET" && method !== "HEAD") headers["X-CSRFToken"] = csrfToken();
  const response = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin" });
  if (response.status === 401 || response.status === 403) {
    location.href = `/login/?next=${encodeURIComponent(location.pathname)}`;
    throw new Error("auth");
  }
  if (!response.ok) throw new Error(`${response.status} on ${path}`);
  return response.status === 204 ? (undefined as T) : response.json();
}

/** Tell the pet something happened (Owner idea #23) — Layout shows a reaction bubble. */
export function petReact(kind: "milestone" | "paper" | "capture" | "note") {
  window.dispatchEvent(new CustomEvent("atlas-pet", { detail: { kind } }));
}

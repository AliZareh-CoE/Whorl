/* Outbound links in the desktop app (owner report 2026-09-06). The Tauri shell refuses to
 * navigate off the local origin, so a plain <a href="https://…"> did nothing there. In the
 * desktop build every click on an external link is routed to the OS browser through the
 * `open_external` command; in a normal browser nothing changes. */

type TauriApi = { core: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> } };

export const isDesktop = () => typeof window !== "undefined" && "__TAURI__" in window;

export async function openExternal(url: string): Promise<boolean> {
  if (!isDesktop()) { window.open(url, "_blank", "noopener"); return true; }
  try {
    const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
    await tauri.core.invoke("open_external", { url });
    return true;
  } catch {
    return false;
  }
}

/** Desktop: open a stored file with the OS default app / show it in the file manager. */
export async function openPath(path: string): Promise<void> {
  const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
  await tauri.core.invoke("open_path", { path });
}
export async function revealPath(path: string): Promise<void> {
  const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
  await tauri.core.invoke("reveal_path", { path });
}

/** Install once: intercept clicks on links that leave this origin. */
export function installExternalLinkHandler(): void {
  if (!isDesktop() || (window as unknown as { __atlasExternal?: boolean }).__atlasExternal) return;
  (window as unknown as { __atlasExternal?: boolean }).__atlasExternal = true;
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey) return;
    const a = (e.target as HTMLElement | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
    if (!a) return;
    let url: URL;
    try { url = new URL(a.href, location.href); } catch { return; }
    if (url.origin === location.origin || !/^(https?:|mailto:)$/.test(url.protocol)) return;
    e.preventDefault();
    void openExternal(url.href);
  }, true);
}

/** Install once (desktop only): swallow the webview's own right-click menu ("Reload", "Back",
 * "Inspect"…) everywhere except text fields, so a right-click on a row shows Atlas's menu and a
 * right-click on empty space shows nothing — never the browser's. */
export function installDesktopContextMenuGuard(): void {
  if (!isDesktop() || (window as unknown as { __atlasCtx?: boolean }).__atlasCtx) return;
  (window as unknown as { __atlasCtx?: boolean }).__atlasCtx = true;
  document.addEventListener("contextmenu", (e) => {
    const el = e.target as HTMLElement | null;
    if (el?.closest?.("input, textarea, [contenteditable], .cm-editor")) return;
    if (!e.defaultPrevented) e.preventDefault();
  });
}

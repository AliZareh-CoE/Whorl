/** Read-aloud with prefetch (#404, backlog #38): long text is split into sentence chunks, the
 *  first chunk plays as soon as it is synthesised and the next one is fetched while it plays,
 *  so a whole abstract reads without gaps or a 5 000-character cut-off. One controller per
 *  listen; stop() ends everything. */
import { csrfToken } from "./api";

export const CHUNK_CHARS = 420;

/** Sentence-aware chunks of at most CHUNK_CHARS (a single very long sentence is split on spaces). */
export function chunkText(text: string, max = CHUNK_CHARS): string[] {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const sentences = clean.split(/(?<=[.!?])\s+(?=[A-Z0-9"“(])/);
  const chunks: string[] = [];
  let current = "";
  const push = () => { if (current.trim()) chunks.push(current.trim()); current = ""; };
  for (const sentence of sentences) {
    if (sentence.length > max) {
      push();
      const words = sentence.split(" ");
      let piece = "";
      for (const w of words) {
        if ((piece + " " + w).trim().length > max) { chunks.push(piece.trim()); piece = w; } else piece = (piece + " " + w).trim();
      }
      if (piece) current = piece;
      continue;
    }
    if ((current + " " + sentence).trim().length > max) push();
    current = (current + " " + sentence).trim();
  }
  push();
  return chunks;
}

async function synthesise(text: string, signal: AbortSignal): Promise<string> {
  const res = await fetch("/tts/", { method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: new URLSearchParams({ text }), signal });
  if (!res.ok) {
    let message = "Read-aloud unavailable.";
    try { message = (await res.json()).error ?? message; } catch { /* not json */ }
    throw new Error(message);
  }
  return URL.createObjectURL(await res.blob());
}

export type Listener = { stop: () => void; done: Promise<void> };

/** Start reading `text`; resolves `done` when the last chunk ends or stop() is called.
 *  `onProgress(i, n)` fires as each chunk starts. Throws (via `done`) on the first failure. */
export function listenTo(text: string, onProgress?: (index: number, total: number) => void): Listener {
  const chunks = chunkText(text);
  const controller = new AbortController();
  let audio: HTMLAudioElement | null = null;
  let stopped = false;
  const urls: string[] = [];
  const cleanup = () => { for (const u of urls) URL.revokeObjectURL(u); };
  const done = (async () => {
    if (chunks.length === 0) return;
    let next: Promise<string> | null = synthesise(chunks[0], controller.signal);
    for (let i = 0; i < chunks.length; i++) {
      if (stopped) break;
      const url = await (next as Promise<string>);
      urls.push(url);
      // prefetch the following chunk while this one plays
      next = i + 1 < chunks.length ? synthesise(chunks[i + 1], controller.signal) : null;
      if (stopped) break;
      onProgress?.(i, chunks.length);
      audio = new Audio(url);
      await new Promise<void>((resolve, reject) => {
        const a = audio as HTMLAudioElement;
        a.onended = () => resolve();
        a.onerror = () => reject(new Error("Playback failed."));
        a.play().catch(reject);
      });
    }
  })().finally(cleanup);
  return {
    stop: () => { stopped = true; controller.abort(); audio?.pause(); },
    done,
  };
}

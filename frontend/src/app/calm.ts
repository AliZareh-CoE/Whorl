/** Calm mode (#274/#278): a zero-config, localStorage-persisted preference (like the theme)
 * that hides the dashboard's monthly vanity stats. Centralised here so any surface — the
 * dashboard toggle, the ⌘K palette verb (#277) — reads/writes the one key and stays in sync
 * live, without a remount: writers dispatch a same-tab event, and we also hear `storage`
 * from other tabs. */
const CALM_KEY = "atlas-calm";
const CALM_EVENT = "atlas-calm-change";

export function readCalm(): boolean {
  try {
    return localStorage.getItem(CALM_KEY) === "1";
  } catch {
    return false;
  }
}

/** Persist + broadcast so every listener (this tab and others) updates immediately. */
export function setCalm(value: boolean): void {
  try {
    localStorage.setItem(CALM_KEY, value ? "1" : "0");
  } catch {
    /* private mode: the custom event below still drives same-session listeners */
  }
  window.dispatchEvent(new CustomEvent(CALM_EVENT, { detail: value }));
}

export function toggleCalm(): boolean {
  const next = !readCalm();
  setCalm(next);
  return next;
}

import { useEffect, useState } from "react";

/** Subscribe to calm mode: re-renders when it changes here or in another tab. */
export function useCalm(): boolean {
  const [calm, setCalmState] = useState(readCalm);
  useEffect(() => {
    const onChange = () => setCalmState(readCalm());
    window.addEventListener(CALM_EVENT, onChange);
    window.addEventListener("storage", onChange); // cross-tab
    return () => {
      window.removeEventListener(CALM_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);
  return calm;
}

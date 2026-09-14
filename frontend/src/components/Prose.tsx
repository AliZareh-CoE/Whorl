/** Rendered markdown from the API (#407): decisions, experiment entries, protocols and
 * captures come with `*_html` companions where [[note]] and @cite-key mentions are already
 * links. The HTML is nh3-sanitized server-side; internal links are picked up by the global
 * SPA link interceptor in Layout, so a mention navigates without a reload.
 * #509: `$math$` arrives as escaped TeX inside .math-inline / .math-display elements and is
 * typeset here with the vendored KaTeX (loaded on first use; works offline in the desktop). */
import { type RefObject, useEffect, useRef } from "react";

const KATEX = { js: "/static/vendor/katex/katex.min.js", css: "/static/vendor/katex/katex.min.css" };
declare global { interface Window { katex?: { render: (tex: string, el: HTMLElement, opts: Record<string, unknown>) => void } } }
let katexLoading: Promise<void> | null = null;
function loadKatex(): Promise<void> {
  if (window.katex) return Promise.resolve();
  if (katexLoading) return katexLoading;
  katexLoading = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${KATEX.css}"]`)) { const link = document.createElement("link"); link.rel = "stylesheet"; link.href = KATEX.css; document.head.appendChild(link); }
    const s = document.createElement("script"); s.src = KATEX.js; s.onload = () => resolve(); s.onerror = () => { katexLoading = null; reject(new Error("KaTeX failed to load")); }; document.head.appendChild(s);
  });
  return katexLoading;
}

/** Typeset every math element under `ref` whenever `html` changes; the TeX source stays if KaTeX is unavailable. */
export function useMath(ref: RefObject<HTMLElement | null>, html: string) {
  useEffect(() => {
    const root = ref.current; if (!root) return;
    const nodes = root.querySelectorAll<HTMLElement>(".math-inline, .math-display"); if (!nodes.length) return;
    let cancelled = false;
    loadKatex().then(() => {
      if (cancelled || !window.katex) return;
      nodes.forEach((el) => { if (el.dataset.rendered) return; const tex = el.textContent ?? ""; try { window.katex!.render(tex, el, { displayMode: el.classList.contains("math-display"), throwOnError: false }); el.dataset.rendered = "1"; } catch { /* keep the source visible */ } });
    }).catch(() => { /* offline without the vendored file: the TeX stays readable */ });
    return () => { cancelled = true; };
  }, [ref, html]);
}

export function Prose({ html, className = "", clamp, testId }: { html: string; className?: string; clamp?: boolean; testId?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useMath(ref, html);
  if (!html) return null;
  return (
    <div
      ref={ref}
      className={`prose prose-sm prose-stone max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline dark:prose-invert dark:prose-a:text-indigo-300 ${clamp ? "line-clamp-4" : ""} ${className}`}
      data-testid={testId}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

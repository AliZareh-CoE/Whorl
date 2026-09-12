/** #459 (backlog #117): which LaTeX environment the cursor sits in, and which completions
 *  deserve to rank first there. Pure functions — no editor imports — so they run under node. */

const BEGIN_END = /\\(begin|end)\{([a-zA-Z*]+)\}/g;

/** The innermost unclosed \begin{…} before the cursor, or null at the top level. */
export function enclosingEnvironment(textBefore: string): string | null {
  const stack: string[] = [];
  const tail = textBefore.length > 20000 ? textBefore.slice(-20000) : textBefore;
  for (const m of tail.matchAll(BEGIN_END)) {
    if (m[1] === "begin") stack.push(m[2]);
    else {
      const i = stack.lastIndexOf(m[2]);
      if (i !== -1) stack.splice(i, 1);
    }
  }
  return stack.length ? stack[stack.length - 1] : null;
}

const LIST = new Set(["itemize", "enumerate", "description"]);
const FLOAT = new Set(["figure", "figure*", "table", "table*"]);
const TABULAR = new Set(["tabular", "tabularx", "tabu", "longtable", "array"]);
const MATH = new Set(["equation", "equation*", "align", "align*", "gather", "gather*", "multline", "eqnarray"]);

/** A ranking bonus for a completion label inside an environment (0 when nothing applies).
 *  Overleaf's usage data: \item dominates lists, \includegraphics and \caption dominate
 *  floats, \hline and \multicolumn dominate tables, \label and \nonumber dominate math. */
export function boostFor(env: string | null, label: string): number {
  if (!env) return 0;
  const l = label.replace(/^\\/, "").replace(/[{[].*$/, "");
  if (LIST.has(env)) return l === "item" ? 99 : 0;
  if (FLOAT.has(env)) return l === "includegraphics" ? 99 : l === "caption" ? 90 : l === "centering" ? 80 : l === "label" ? 70 : 0;
  if (TABULAR.has(env)) return l === "hline" ? 99 : l === "multicolumn" ? 90 : l === "toprule" || l === "midrule" || l === "bottomrule" ? 85 : 0;
  if (MATH.has(env)) return l === "label" ? 99 : l === "nonumber" ? 80 : l === "frac" ? 60 : 0;
  return 0;
}

// Post-build: replace Vite's emitted preload helper with a trivial, conservative module.
//
// The islands build has modulePreload off and emits no CSS, so every __vitePreload call
// carries an empty dependency list and the helper only ever needs to run the import. Vite 8
// still wraps each dynamic import with it and emits the helper as its own chunk; a desktop
// WebView (Edge 152) refused to parse that chunk ("Unexpected strict mode reserved word"),
// which blanked the whole app because spa.js imports it. A three-token helper cannot fail
// to parse anywhere. The exported alias is read from the emitted file so importers keep
// resolving; a helper that does not look like Vite's is left alone and reported.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const file = resolve(process.argv[2] ?? "../static/js/islands/preload-helper-chunk.js");
if (!existsSync(file)) { console.log("simplify-preload: no helper emitted, nothing to do"); process.exit(0); }
const src = readFileSync(file, "utf8");
const m = src.match(/export\s*\{\s*(\w+)\s+as\s+(\w+)\s*\}/);
if (!m) { console.error("simplify-preload: could not find the helper's export in " + file); process.exit(1); }
const [, local, alias] = m;
const out = `function ${local}(e){return e()}export{${local} as ${alias}};\n`;
writeFileSync(file, out);
console.log(`simplify-preload: ${file} → ${out.trim()}`);

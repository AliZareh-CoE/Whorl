import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Islands build: each entry becomes one self-contained ES module under
// static/js/islands/, loaded lazily by static/js/islands-loader.js.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, "../static/js"),
    emptyOutDir: false, // static/js also holds the hand-written islands-loader.js
    // assets live under /static/js/, not the site base, so Vite's preload helper
    // builds wrong URLs (a 404 per dynamic import); native import() resolves
    // module-relative and needs no preloading here
    modulePreload: false,
    rollupOptions: {
      // keep each entry's default export — the loader calls mod.default(el, props)
      preserveEntrySignatures: "exports-only",
      input: {
        "documents-table": resolve(__dirname, "src/islands/documents-table.tsx"),
        assistant: resolve(__dirname, "src/islands/assistant.tsx"),
        "latex-editor": resolve(__dirname, "src/editor/index.ts"),
        spa: resolve(__dirname, "src/app/main.tsx"),
      },
      output: {
        format: "es",
        entryFileNames: (chunk) =>
          chunk.name === "spa"
            ? "spa.js"
            : chunk.name === "latex-editor"
              ? "latex-editor-cm6.js" // Slice A: build alongside CM5; cut over in B/C
              : "islands/[name].js",
        chunkFileNames: (chunk) => {
          // the editor entry splits once vim became a dynamic import (#137):
          // name its two halves instead of shipping opaque index-chunk files
          if (chunk.moduleIds.some((m) => m.includes("codemirror-vim")))
            return "islands/vim-keymap-chunk.js";
          if (chunk.moduleIds.some((m) => m.includes("/src/editor/")))
            return "islands/latex-editor-core-chunk.js";
          return "islands/[name]-chunk.js";
        },
        assetFileNames: "islands/[name][extname]",
      },
    },
  },
});
